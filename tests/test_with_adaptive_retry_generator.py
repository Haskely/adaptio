import asyncio
import unittest

from adaptio import ServiceOverloadError, with_adaptive_retry


class TestWithAdaptiveRetryGenerator(unittest.TestCase):
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
            @with_adaptive_retry(max_retries=0)
            async def simple_generator():
                for i in range(5):
                    yield i

            results = []
            async for item in simple_generator():
                results.append(item)

            self.assertEqual(results, [0, 1, 2, 3, 4])

        self.loop.run_until_complete(test())

    def test_generator_auto_retry_on_overload(self):
        """测试生成器过载重试"""

        async def test():
            attempts = 0

            @with_adaptive_retry(max_retries=3, retry_interval_seconds=0.1)
            async def failing_generator():
                nonlocal attempts
                attempts += 1

                # 前两次失败，第三次成功
                if attempts < 3:
                    # 第一次尝试会产生一个item，然后失败
                    if attempts == 1:
                        yield "item-attempt-1"
                    raise ServiceOverloadError("Service overloaded")

                # 第三次成功
                for i in range(3):
                    yield f"item-{i}"

            results = []
            async for item in failing_generator():
                results.append(item)

            # 验证重试次数
            self.assertEqual(attempts, 3)
            # 验证收到的数据（包含第一次尝试的数据）
            # 注意：由于生成器重试会重新执行整个生成器，
            # 第一次尝试产生的数据会被包含在结果中
            self.assertEqual(results, ["item-attempt-1", "item-0", "item-1", "item-2"])

        self.loop.run_until_complete(test())

    def test_generator_max_retries_exceeded(self):
        """测试超过最大重试次数"""

        async def test():
            attempts = 0

            @with_adaptive_retry(max_retries=2, retry_interval_seconds=0.1)
            async def always_failing_generator():
                nonlocal attempts
                attempts += 1
                raise ServiceOverloadError("Always fail")
                yield  # 永远不会执行到这里

            with self.assertRaises(ServiceOverloadError):
                async for _ in always_failing_generator():
                    pass

            # 初始尝试 + 2次重试 = 3次
            self.assertEqual(attempts, 3)

        self.loop.run_until_complete(test())

    def test_generator_with_non_overload_exception(self):
        """测试非过载异常不触发重试"""

        async def test():
            attempts = 0

            @with_adaptive_retry(max_retries=5)
            async def generator_with_value_error():
                nonlocal attempts
                attempts += 1
                yield "item-1"
                raise ValueError("This should not retry")

            items = []
            with self.assertRaises(ValueError):
                async for item in generator_with_value_error():
                    items.append(item)

            # 应该只尝试一次，不重试
            self.assertEqual(attempts, 1)
            self.assertEqual(items, ["item-1"])

        self.loop.run_until_complete(test())

    def test_normal_async_function_still_works(self):
        """确保普通异步函数仍然正常工作"""

        async def test():
            call_count = 0

            @with_adaptive_retry(max_retries=3, retry_interval_seconds=0.1)
            async def normal_async_func(value: int) -> int:
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ServiceOverloadError("Overloaded")
                return value * 2

            result = await normal_async_func(5)
            self.assertEqual(result, 10)
            self.assertEqual(call_count, 2)

        self.loop.run_until_complete(test())

    def test_generator_with_args_and_kwargs(self):
        """测试生成器支持参数和关键字参数"""

        async def test():
            @with_adaptive_retry()
            async def generator_with_params(start: int, end: int, step: int = 1):
                for i in range(start, end, step):
                    yield i

            results = []
            async for item in generator_with_params(0, 10, 2):
                results.append(item)

            self.assertEqual(results, [0, 2, 4, 6, 8])

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
