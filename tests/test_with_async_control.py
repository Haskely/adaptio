import asyncio
import unittest

from adaptio import with_async_control


class TestWithAsyncControl(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_with_async_control(self):
        async def test_control():
            executed_tasks = []

            @with_async_control(max_concurrency=2)
            async def controlled_task(task_id):
                executed_tasks.append(task_id)
                await asyncio.sleep(0.1)
                return task_id

            tasks = [controlled_task(i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            self.assertEqual(len(results), 5)
            self.assertEqual(set(results), {0, 1, 2, 3, 4})
            self.assertEqual(len(executed_tasks), 5)

        self.loop.run_until_complete(test_control())

    def test_with_async_control_error_handling(self):
        async def test_control_error():
            retry_count = 0

            @with_async_control(cared_exception=ValueError, retry_n=2, retry_delay=0.1)
            async def failing_task():
                nonlocal retry_count
                retry_count += 1
                raise ValueError("Test error")

            with self.assertRaises(ValueError):
                await failing_task()

            # 验证重试次数：初始尝试 + 2次重试 = 3次
            self.assertEqual(retry_count, 3)

        self.loop.run_until_complete(test_control_error())

    def test_with_async_control_callable_exception_handler(self):
        async def test_control_callable():
            retry_count = 0

            def exception_handler(e: Exception) -> bool:
                return isinstance(e, ValueError) and str(e).startswith("Retry")

            @with_async_control(
                cared_exception=exception_handler, retry_n=100, retry_delay=0.1
            )
            async def selective_failing_task():
                nonlocal retry_count
                retry_count += 1
                if retry_count <= 2:
                    raise ValueError("Retry this error")
                raise ValueError("Don't retry this error")

            with self.assertRaises(ValueError):
                await selective_failing_task()

            # 验证只有符合条件的错误会触发重试
            self.assertEqual(retry_count, 3)

        self.loop.run_until_complete(test_control_callable())


if __name__ == "__main__":
    unittest.main()
