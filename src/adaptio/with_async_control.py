import asyncio
import weakref
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from adaptio.decorator_utils import (
    is_async_generator_function,
    rewrap_static_class_method,
    unwrap_static_class_method,
)
from adaptio.log_utils import setup_colored_logger

P = ParamSpec("P")
T = TypeVar("T")

# 设置logger
logger = setup_colored_logger(__name__)


class LoopLocalLock:
    """
    LoopLocalLock: 为每个 event loop 自动分配一把 asyncio.Lock。

    - 同一个 LoopLocalLock 实例，可以在多个线程 / 多个 event loop 下使用。
    - 每个 loop 拿到的都是"自己的那把 asyncio.Lock"，互相之间独立，不共享状态。
    - 主要用途：避免 asyncio.Lock 在多线程、多 loop 场景下的
      "RuntimeError: <Lock ...> is bound to a different event loop"。

    注意：
    ----
    这个类 **不是** 跨 loop / 跨线程互斥。
    它提供的是"按 loop 局部互斥"，更多是为了代码架构上的方便，避免错误。
    如果你需要跨线程全局互斥，请使用 threading.Lock。
    """

    def __init__(self) -> None:
        # key: loop (弱引用), value: asyncio.Lock (强引用)
        self._locks: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, asyncio.Lock
        ] = weakref.WeakKeyDictionary()

    def _get_current_loop(self) -> asyncio.AbstractEventLoop:
        """
        获取当前正在运行的 event loop。
        必须在 coroutine 中调用（即有 running loop）。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 在未运行的线程 / 非 coroutine 环境下调用会报错。
            raise RuntimeError(
                "LoopLocalLock must be used inside an asyncio event loop "
                "(i.e., inside an `async def` function)."
            ) from None
        return loop

    def _get_lock_for_current_loop(self) -> asyncio.Lock:
        """
        获取当前 loop 对应的 asyncio.Lock。
        若不存在则新建一个并缓存。
        """
        loop = self._get_current_loop()
        lock = self._locks.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[loop] = lock
        return lock

    # ---------- 公共 API，与 asyncio.Lock 保持尽量一致 ----------

    def locked(self) -> bool:
        """
        返回当前 loop 下的那把锁是否已被 acquire。
        不同 loop 之间互不影响。
        """
        lock = self._get_lock_for_current_loop()
        return lock.locked()

    async def acquire(self) -> bool:
        """
        在当前 loop 下 acquire 对应的 asyncio.Lock。
        """
        lock = self._get_lock_for_current_loop()
        return await lock.acquire()

    def release(self) -> None:
        """
        在当前 loop 下 release 对应的 asyncio.Lock。
        """
        lock = self._get_lock_for_current_loop()
        lock.release()

    # 支持 async with 语法
    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()


class FakeLock:
    """空锁实现，用于不需要并发控制时"""

    async def __aenter__(self) -> "FakeLock":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        return None


def with_async_control(
    cared_exception: type[Exception]
    | tuple[type[Exception], ...]
    | Callable[[Exception], bool] = Exception,
    max_concurrency: int = 0,
    max_qps: float = 0,
    retry_n: int = 0,
    retry_delay: float = 1.0,
    ignore_loop_bound_exception: bool = True,
):
    """
    异步函数或异步生成器的装饰器，提供并发限制、QPS控制和重试功能

    自动检测被装饰的函数类型：
    - 普通异步函数 (async def func() -> T): 对函数调用进行控制
    - 异步生成器 (async def func() -> AsyncGenerator[T, None]): 对生成器迭代进行控制

    参数:
        cared_exception: 需要捕获的异常类型或者一个输入为异常对象的函数
        max_concurrency: 最大并发数 (0表示不限制)
        max_qps: 每秒最大请求数 (0表示不限制)
        retry_n: 重试次数
        retry_delay: 重试间隔时间(秒)
        ignore_loop_bound_exception: 是否使用 LoopLocalLock 以支持多线程兼容性
            如果为 True (默认), 将使用 LoopLocalLock 来适配多线程 + 多 loop 场景
            如果为 False, 将使用标准的 asyncio.Lock，可能在多 loop 场景下抛出 RuntimeError

    返回:
        装饰器函数

    Example:
        ```python
        # 装饰普通异步函数
        @with_async_control(max_concurrency=5, retry_n=3)
        async def fetch_data(url: str) -> dict:
            async with session.get(url) as resp:
                return await resp.json()

        # 装饰异步生成器（自动检测）
        @with_async_control(max_concurrency=3, retry_n=2)
        async def fetch_pages(base_url: str):
            for page in range(1, 100):
                data = await fetch_page(f"{base_url}?page={page}")
                for item in data:
                    yield item
        ```
    """
    retry_n = int(max(retry_n, 0))

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        # 为每个装饰器实例创建独立的锁
        concurrency_sem = (
            asyncio.Semaphore(max_concurrency) if max_concurrency > 0 else FakeLock()
        )

        if ignore_loop_bound_exception:
            qps_lock = LoopLocalLock()
            if max_qps > 1e-5:  # 只在实际使用 QPS 限制时才记录 warning
                logger.warning(
                    f"with_async_control for function '{func.__name__}' initialized with LoopLocalLock for multi-threading compatibility. "
                    "Note: This provides per-loop local locking, not cross-loop/cross-thread mutex. "
                    "Set ignore_loop_bound_exception=False if you want standard asyncio.Lock behavior."
                )
        else:
            qps_lock = asyncio.Lock()

        # 🔍 兼容性处理：检测是否被 staticmethod/classmethod 包装
        actual_func, is_static, is_class = unwrap_static_class_method(func)

        # 🔍 关键：检测函数类型
        is_async_gen = is_async_generator_function(func)

        if is_async_gen:
            # ========== 异步生成器处理逻辑 ==========
            @wraps(actual_func)  # type: ignore[arg-type]
            async def generator_wrapper(*args, **kwargs):
                async with concurrency_sem:
                    for attempt in range(retry_n + 1):
                        try:
                            if max_qps > 1e-5:  # 避免浮点数精度问题
                                async with qps_lock:
                                    await asyncio.sleep(1 / max_qps)

                            # 创建并迭代生成器
                            generator = actual_func(*args, **kwargs)  # type: ignore[misc,operator]
                            item_count = 0

                            async for item in generator:
                                yield item
                                item_count += 1

                            # 成功完成
                            logger.debug(
                                f"{actual_func.__name__} -- 生成器成功完成，产出 {item_count} 个项目"
                            )
                            return  # 成功退出

                        except Exception as e:
                            if retry_n <= 0:
                                raise
                            if callable(cared_exception):
                                if not cared_exception(e):
                                    raise
                            elif not isinstance(e, cared_exception):
                                raise

                            logger.error(
                                f"（{attempt + 1}/{retry_n}） 尝试生成器 {actual_func.__name__} 失败: \n Class: {e.__class__.__name__}\n Message: {e}"
                            )

                            if attempt >= retry_n:
                                logger.error(
                                    f"（{attempt + 1}/{retry_n}） 尝试生成器 {actual_func.__name__} 达到最大次数！"
                                )
                                raise

                            await asyncio.sleep(retry_delay)
                            continue  # 重新开始

                raise Exception("所有重试都失败了")

            # 如果原来是 staticmethod/classmethod，需要重新包装
            return rewrap_static_class_method(generator_wrapper, is_static, is_class)  # type: ignore[return-value]

        else:
            # ========== 普通异步函数处理逻辑（保持原有实现）==========
            @wraps(actual_func)  # type: ignore[arg-type]
            async def function_wrapper(*args, **kwargs):
                async with concurrency_sem:
                    for attempt in range(retry_n + 1):
                        try:
                            if max_qps > 1e-5:  # 避免浮点数精度问题
                                async with qps_lock:
                                    await asyncio.sleep(1 / max_qps)
                            return await actual_func(*args, **kwargs)  # type: ignore[misc]
                        except Exception as e:
                            if retry_n <= 0:
                                raise
                            if callable(cared_exception):
                                if not cared_exception(e):
                                    raise
                            elif not isinstance(e, cared_exception):
                                raise
                            logger.error(
                                f"（{attempt + 1}/{retry_n}） 尝试 {actual_func.__name__} 失败: \n Class: {e.__class__.__name__}\n Message: {e}"
                            )
                            if attempt >= retry_n:
                                logger.error(
                                    f"（{attempt + 1}/{retry_n}） 尝试 {actual_func.__name__} 达到最大次数！"
                                )
                                raise
                            await asyncio.sleep(retry_delay)
                    raise Exception("所有重试都失败了")

            # 如果原来是 staticmethod/classmethod，需要重新包装
            return rewrap_static_class_method(function_wrapper, is_static, is_class)  # type: ignore[return-value]

    return decorator


if __name__ == "__main__":
    import time

    @with_async_control(
        cared_exception=ValueError,
        max_concurrency=5,
        max_qps=10,
        retry_n=3,
        retry_delay=0.5,
    )
    async def test_api(i: int) -> str:
        # 模拟一个可能失败的API调用
        if i % 3 == 2:  # 让每三个请求中的一个失败
            raise ValueError(f"模拟 ValueError错误 - 请求 {i}")
        if i % 3 == 1:
            raise RuntimeError(f"模拟 RuntimeError 错误 - 请求 {i}")
        await asyncio.sleep(1.0)  # 模拟API延迟
        return f"请求 {i} 成功"

    async def main():
        print("开始测试...")
        start_time = time.time()

        # 创建5个并发任务
        tasks = [test_api(i) for i in range(10)]

        # 打印结果
        for i, future in enumerate(asyncio.as_completed(tasks)):
            try:
                result = await future
                logger.info(f"任务 {i} 成功: {result}")
            except Exception as e:
                logger.warning(
                    f"任务 {i} 失败: \n Class: {e.__class__.__name__}\n Message: {e}"
                )

        end_time = time.time()
        print(f"\n总耗时: {end_time - start_time:.2f}秒")

    # 运行测试
    # asyncio.run(main())

    @with_async_control(
        cared_exception=ValueError,
        max_concurrency=5,
        max_qps=10,
        retry_n=3,
        retry_delay=0.5,
    )
    async def test_api_generator(i: int):
        for j in range(3):
            await asyncio.sleep(0.1)
            yield str(f"子项目 {j}")
        await asyncio.sleep(1.0)  # 模拟API延迟
        # 模拟一个可能失败的API调用
        if i % 3 == 2:  # 让每三个请求中的一个失败
            raise ValueError(f"模拟 ValueError错误 - 请求 {i}")
        if i % 3 == 1:
            raise RuntimeError(f"模拟 RuntimeError 错误 - 请求 {i}")

        yield f"请求 {i} 成功"

    async def main_generator():
        print("开始测试 generator...")
        start_time = time.time()

        from collections.abc import AsyncGenerator

        async def call_generator(agen: AsyncGenerator[str]) -> None:
            async for item in agen:
                print(item)

        # 创建5个并发任务
        tasks = [call_generator(test_api_generator(i)) for i in range(10)]

        # 打印结果
        for i, future in enumerate(asyncio.as_completed(tasks)):
            try:
                result = await future
                logger.info(f"任务 {i} 成功: {result}")
            except Exception as e:
                logger.warning(
                    f"任务 {i} 失败: \n Class: {e.__class__.__name__}\n Message: {e}"
                )

        end_time = time.time()
        print(f"\n总耗时: {end_time - start_time:.2f}秒")

    # 运行测试
    asyncio.run(main_generator())
