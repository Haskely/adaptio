import asyncio
import unittest

from adaptio import with_async_control


class TestWithAsyncControlGenerator(unittest.TestCase):
    def __init__(self, *args: str, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.loop: asyncio.AbstractEventLoop

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_generator_basic_functionality(self):
        """测试生成器基本功能"""

        async def test():
            @with_async_control(max_concurrency=2)
            async def simple_generator():
                for i in range(5):
                    await asyncio.sleep(0.01)
                    yield i

            results = []
            async for item in simple_generator():
                results.append(item)

            self.assertEqual(results, [0, 1, 2, 3, 4])

        self.loop.run_until_complete(test())

    def test_generator_with_retry(self):
        """测试生成器重试功能"""

        async def test():
            attempts = 0

            @with_async_control(cared_exception=ValueError, retry_n=3, retry_delay=0.05)
            async def failing_generator():
                nonlocal attempts
                attempts += 1

                # 前两次失败，第三次成功
                if attempts < 3:
                    if attempts == 1:
                        yield "item-attempt-1"
                    raise ValueError("Simulated error")

                # 第三次成功
                for i in range(3):
                    yield f"item-{i}"

            results = []
            async for item in failing_generator():
                results.append(item)

            # 验证重试次数
            self.assertEqual(attempts, 3)
            # 验证收到的数据（包含第一次尝试的数据）
            self.assertEqual(results, ["item-attempt-1", "item-0", "item-1", "item-2"])

        self.loop.run_until_complete(test())

    def test_generator_max_retries_exceeded(self):
        """测试超过最大重试次数"""

        async def test():
            attempts = 0

            @with_async_control(cared_exception=ValueError, retry_n=2, retry_delay=0.05)
            async def always_failing_generator():
                nonlocal attempts
                attempts += 1
                raise ValueError("Always fail")
                yield  # 永远不会执行到这里

            with self.assertRaises(ValueError):
                async for _ in always_failing_generator():
                    pass

            # 初始尝试 + 2次重试 = 3次
            self.assertEqual(attempts, 3)

        self.loop.run_until_complete(test())

    def test_generator_with_qps_limit(self):
        """测试生成器的QPS限制"""

        async def test():
            import time

            @with_async_control(max_qps=5)  # 每秒5个请求
            async def rate_limited_generator():
                for i in range(3):
                    yield i

            start_time = time.time()
            results = []
            async for item in rate_limited_generator():
                results.append(item)
            elapsed = time.time() - start_time

            self.assertEqual(results, [0, 1, 2])
            # QPS=5意味着每个请求间隔0.2秒，3个请求至少需要0.2秒
            self.assertGreaterEqual(elapsed, 0.2)

        self.loop.run_until_complete(test())

    def test_generator_with_callable_exception_handler(self):
        """测试使用可调用的异常处理器"""

        async def test():
            attempts = 0

            def should_retry(e: Exception) -> bool:
                return "retry" in str(e).lower()

            @with_async_control(
                cared_exception=should_retry, retry_n=2, retry_delay=0.05
            )
            async def conditional_retry_generator():
                nonlocal attempts
                attempts += 1

                if attempts == 1:
                    yield "item-1"
                    raise ValueError("Please retry this")
                elif attempts == 2:
                    for i in range(2):
                        yield f"item-{i}"

            results = []
            async for item in conditional_retry_generator():
                results.append(item)

            self.assertEqual(attempts, 2)
            self.assertEqual(results, ["item-1", "item-0", "item-1"])

        self.loop.run_until_complete(test())

    def test_normal_async_function_still_works(self):
        """确保普通异步函数仍然正常工作"""

        async def test():
            call_count = 0

            @with_async_control(cared_exception=ValueError, retry_n=2, retry_delay=0.05)
            async def normal_async_func(value: int) -> int:
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ValueError("Need retry")
                return value * 2

            result = await normal_async_func(5)
            self.assertEqual(result, 10)
            self.assertEqual(call_count, 2)

        self.loop.run_until_complete(test())

    def test_generator_with_concurrency_limit(self):
        """测试生成器的并发限制"""

        async def test():
            running_count = 0
            max_running = 0

            @with_async_control(max_concurrency=2)
            async def concurrent_generator(gen_id: int):
                nonlocal running_count, max_running
                running_count += 1
                max_running = max(max_running, running_count)

                await asyncio.sleep(0.1)
                for i in range(3):
                    yield f"gen-{gen_id}-item-{i}"

                running_count -= 1

            # 创建3个生成器并发运行
            generators = [concurrent_generator(i) for i in range(3)]

            async def consume(gen) -> list[str]:
                items: list[str] = []
                async for item in gen:
                    items.append(item)  # type: ignore[arg-type]
                return items

            results = await asyncio.gather(*[consume(g) for g in generators])  # type: ignore[arg-type]

            # 验证所有生成器都成功完成
            self.assertEqual(len(results), 3)
            for _i, items in enumerate(results):  # type: ignore[var-annotated]
                self.assertEqual(len(items), 3)  # type: ignore[arg-type]

            # 验证并发数受到限制（应该不超过2）
            self.assertLessEqual(max_running, 2)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
