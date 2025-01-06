import asyncio


class AdjustableSemaphore:
    """可调整容量的异步信号量

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

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


if __name__ == "__main__":
    import random
    import time

    current_working_count = 0

    async def worker(sem: AdjustableSemaphore, worker_id: int):
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

    async def dynamic_controller(sem: AdjustableSemaphore):
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
