import asyncio
import unittest

from adaptio import ServiceOverloadError, with_adaptive_retry


class TestWithAdaptiveRetry(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_auto_retry_on_overload(self) -> None:
        async def test_retry() -> None:
            attempts = 0

            @with_adaptive_retry(max_retries=3)
            async def failing_task() -> bool:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise ServiceOverloadError("Service overloaded")
                return True

            result = await failing_task()
            self.assertTrue(result)
            self.assertEqual(attempts, 3)

        self.loop.run_until_complete(test_retry())

    def test_max_retries_exceeded(self) -> None:
        async def test_retry() -> None:
            attempts = 0

            @with_adaptive_retry(max_retries=2)
            async def failing_task() -> bool:
                nonlocal attempts
                attempts += 1
                raise ServiceOverloadError("Service overloaded")

            with self.assertRaises(ServiceOverloadError):
                await failing_task()
            self.assertEqual(attempts, 3)  # 初始尝试 + 2次重试

        self.loop.run_until_complete(test_retry())

    def test_retry_with_different_exception(self) -> None:
        async def test_retry() -> None:
            @with_adaptive_retry(max_retries=2)
            async def failing_task() -> None:
                raise ValueError("Different error")

            with self.assertRaises(ValueError):
                await failing_task()

        self.loop.run_until_complete(test_retry())


if __name__ == "__main__":
    unittest.main()
