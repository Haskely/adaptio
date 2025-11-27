import asyncio
import weakref
from typing import Union

from loguru import logger


class _AdjustableSemaphoreBase:
    """可调整容量的异步信号量基类

    这个信号量允许在运行时动态调整最大并发数。

    Args:
        initial_value (int): 初始的信号量值（最大并发数）

    Raises:
        ValueError: 当尝试设置负数值时抛出
    """

    def __init__(self, initial_value: int = 1) -> None:
        if initial_value < 0:
            raise ValueError("Initial semaphore value cannot be negative")
        self.initial_value = initial_value
        self._current_value = initial_value
        self._condition = asyncio.Condition()

    async def acquire(self) -> bool:
        """获取信号量"""
        async with self._condition:
            while self._current_value <= 0:
                await self._condition.wait()
            self._current_value -= 1
            return True

    async def release(self) -> None:
        """释放信号量"""
        async with self._condition:
            self._current_value += 1
            self._condition.notify(1)

    async def set_value(self, value: int) -> None:
        """动态设置新的并发数量"""
        if value < 0:
            raise ValueError("Semaphore value cannot be negative")

        async with self._condition:
            delta = value - self.initial_value
            self.initial_value = value
            self._current_value += delta

            # 如果新值增加了，唤醒等待的协程
            if delta > 0:
                self._condition.notify(delta)

    def get_value(self) -> int:
        """获取当前信号量的值"""
        return self._current_value

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


def AdjustableSemaphore(
    initial_value: int = 1, ignore_loop_bound_exception: bool = False
) -> Union["_AdjustableSemaphoreBase", "LoopLocalAdjustableSemaphore"]:
    """创建可调整容量的异步信号量

    这是一个工厂函数，根据 ignore_loop_bound_exception 参数返回适当的信号量实现：
    - False（默认）: 返回标准的信号量实例，在跨 loop 使用时会抛出 RuntimeError
    - True: 返回 LoopLocalAdjustableSemaphore，每个 loop 有独立的信号量实例

    Args:
        initial_value: 初始的信号量值（最大并发数）
        ignore_loop_bound_exception: 是否使用 loop-local 信号量
            - False（推荐）: 标准行为，跨 loop 使用时抛出错误
            - True: 为每个 loop 创建独立的信号量，适合多线程场景

    Returns:
        信号量实例（_AdjustableSemaphoreBase 或 LoopLocalAdjustableSemaphore）

    Example:
        ```python
        # 标准用法（单 loop）
        sem = AdjustableSemaphore(initial_value=2)

        # 多线程用法
        sem = AdjustableSemaphore(initial_value=2, ignore_loop_bound_exception=True)
        ```
    """
    # 延迟导入以避免循环引用
    if ignore_loop_bound_exception:
        logger.info(
            "Creating LoopLocalAdjustableSemaphore for multi-threading compatibility. "
            "Each event loop will have its own independent semaphore instance."
        )
        return LoopLocalAdjustableSemaphore(initial_value=initial_value)
    else:
        return _AdjustableSemaphoreBase(initial_value=initial_value)


class LoopLocalAdjustableSemaphore:
    """为每个 event loop 自动分配独立的信号量

    这个类解决了在多线程多 loop 场景下使用信号量的问题：
    - 每个 event loop 拥有自己独立的信号量实例
    - 不同 loop 之间互不干扰，各自独立计数
    - 适合多线程场景，每个线程有自己的 loop 和信号量限制

    注意：
    ----
    - 这个类提供的是"按 loop 局部限制"，不是全局限制
    - 如果你需要跨所有 loop 的全局并发限制，应该使用其他方案
    - 每个 loop 的信号量容量可以独立调整（通过 set_value）

    适用场景：
    --------
    1. ✅ 多线程多 loop，每个线程需要独立的并发控制
    2. ✅ 多次 asyncio.run() 调用，避免 loop bound 错误
    3. ❌ 需要跨所有 loop 的全局并发限制（这种情况请用 threading.Semaphore）

    Example:
        ```python
        # 推荐使用工厂函数创建
        sem = AdjustableSemaphore(initial_value=2, ignore_loop_bound_exception=True)

        # 或者直接创建
        sem = LoopLocalAdjustableSemaphore(initial_value=2)

        def run_in_thread():
            async def worker():
                # 每个线程的 loop 自动获取独立的信号量
                async with sem:
                    await asyncio.sleep(0.1)
            asyncio.run(worker())

        # 多个线程，每个都有独立的信号量限制
        threading.Thread(target=run_in_thread).start()
        threading.Thread(target=run_in_thread).start()
        ```
    """

    def __init__(self, initial_value: int = 1) -> None:
        """初始化 LoopLocalAdjustableSemaphore

        Args:
            initial_value: 每个 loop 的信号量初始值（最大并发数）

        Raises:
            ValueError: 当 initial_value 为负数时
        """
        if initial_value < 0:
            raise ValueError("Initial semaphore value cannot be negative")
        self._initial_value_config = initial_value
        # key: loop (弱引用), value: _AdjustableSemaphoreBase (强引用)
        self._semaphores: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, _AdjustableSemaphoreBase
        ] = weakref.WeakKeyDictionary()

    def _get_current_loop(self) -> asyncio.AbstractEventLoop:
        """获取当前运行的 event loop

        Returns:
            当前运行的 event loop

        Raises:
            RuntimeError: 如果不在 async 上下文中调用
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError(
                "LoopLocalAdjustableSemaphore must be used inside an asyncio event loop "
                "(i.e., inside an `async def` function)."
            ) from None
        return loop

    def _get_semaphore_for_current_loop(self) -> _AdjustableSemaphoreBase:
        """获取当前 loop 对应的信号量

        如果当前 loop 还没有对应的信号量，会自动创建一个。

        Returns:
            当前 loop 对应的信号量实例
        """
        loop = self._get_current_loop()
        sem = self._semaphores.get(loop)
        if sem is None:
            # 为这个 loop 创建新的信号量实例
            sem = _AdjustableSemaphoreBase(initial_value=self._initial_value_config)
            self._semaphores[loop] = sem
            logger.debug(
                f"Created new semaphore for loop {id(loop)} "
                f"with initial_value={self._initial_value_config}"
            )
        return sem

    async def acquire(self) -> bool:
        """获取当前 loop 的信号量

        Returns:
            True 表示成功获取
        """
        sem = self._get_semaphore_for_current_loop()
        return await sem.acquire()

    async def release(self) -> None:
        """释放当前 loop 的信号量"""
        sem = self._get_semaphore_for_current_loop()
        await sem.release()

    async def set_value(self, value: int) -> None:
        """动态设置当前 loop 的信号量容量

        注意：这只会影响当前 loop 的信号量，不影响其他 loop。

        Args:
            value: 新的信号量容量

        Raises:
            ValueError: 当 value 为负数时
        """
        if value < 0:
            raise ValueError("Semaphore value cannot be negative")

        sem = self._get_semaphore_for_current_loop()
        await sem.set_value(value)

    def get_value(self) -> int:
        """获取当前 loop 的信号量值

        Returns:
            当前 loop 的信号量可用容量
        """
        sem = self._get_semaphore_for_current_loop()
        return sem.get_value()

    def get_initial_value_config(self) -> int:
        """获取初始值配置

        Returns:
            配置的初始值（新 loop 会使用这个值）
        """
        return self._initial_value_config

    @property
    def initial_value(self) -> int:
        """获取当前 loop 的信号量的 initial_value

        这个属性返回当前 event loop 对应的信号量实例的 initial_value。
        如果调用了 set_value() 修改了信号量容量，这个值也会相应更新。

        Returns:
            当前 loop 的信号量的 initial_value（可能已通过 set_value 修改）
        """
        sem = self._get_semaphore_for_current_loop()
        return sem.initial_value

    async def __aenter__(self):
        """支持 async with 语法"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持 async with 语法"""
        await self.release()


# 类型别名，用于类型提示
AdjustableSemaphoreType = _AdjustableSemaphoreBase | LoopLocalAdjustableSemaphore


if __name__ == "__main__":
    import random
    import time

    current_working_count = 0

    async def worker(sem: AdjustableSemaphoreType, worker_id: int):
        """模拟工作任务"""
        async with sem:
            global current_working_count
            current_working_count += 1
            print(
                f"[{time.strftime('%H:%M:%S')}] 工作者 {worker_id} 开始执行，当前并发数：{sem.initial_value - sem.get_value()} 当前工作协程数：{current_working_count}"
            )
            await asyncio.sleep(random.uniform(2, 5))  # 模拟耗时操作
            print(f"[{time.strftime('%H:%M:%S')}] 工作者 {worker_id} 完成")
            current_working_count -= 1

    async def dynamic_controller(sem: AdjustableSemaphoreType):
        """动态控制并发数量"""
        print(f"\n[{time.strftime('%H:%M:%S')}] 初始并发数为 {sem.initial_value}")
        await asyncio.sleep(10)  # 等待一些任务开始执行

        print(f"\n[{time.strftime('%H:%M:%S')}] 将并发数调整为 2")
        await sem.set_value(2)
        await asyncio.sleep(10)

        print(f"\n[{time.strftime('%H:%M:%S')}] 将并发数调整为 7")
        await sem.set_value(7)
        await asyncio.sleep(10)

        print(f"\n[{time.strftime('%H:%M:%S')}] 将并发数调整为 3")
        await sem.set_value(3)
        await asyncio.sleep(10)

        print(f"\n[{time.strftime('%H:%M:%S')}] 将并发数调整为 1")
        await sem.set_value(1)
        await asyncio.sleep(10)

        print(f"\n[{time.strftime('%H:%M:%S')}] 将并发数调整为 0")
        await sem.set_value(0)
        await asyncio.sleep(10)

        print(f"\n[{time.strftime('%H:%M:%S')}] 将并发数调整为 20")
        await sem.set_value(20)

    async def main():
        # 初始并发数为 3
        sem = AdjustableSemaphore(5)

        # 创建 100 个工作任务
        workers = [worker(sem, i) for i in range(100)]

        # 创建动态控制任务
        controller = dynamic_controller(sem)

        # 同时运行所有任务
        await asyncio.gather(controller, *workers)

    if __name__ == "__main__":
        asyncio.run(main())
