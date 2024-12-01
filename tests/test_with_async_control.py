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
            @with_async_control(max_concurrency=2)
            async def failing_task():
                raise ValueError("Test error")

            with self.assertRaises(ValueError):
                await failing_task()

        self.loop.run_until_complete(test_control_error())


if __name__ == "__main__":
    unittest.main()
