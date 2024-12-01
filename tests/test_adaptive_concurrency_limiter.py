import asyncio
import unittest

from adaptio import AdaptiveAsyncConcurrencyLimiter


class TestAdaptiveConcurrencyLimiter(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_dynamic_task_scheduler(self):
        async def test_scheduler():
            scheduler = AdaptiveAsyncConcurrencyLimiter(max_concurrency=2)

            # 添加任务执行时间跟踪
            start_time = asyncio.get_event_loop().time()
            execution_times = []

            async def sample_task(task_id):
                task_start = asyncio.get_event_loop().time()
                await asyncio.sleep(0.1)  # 增加延迟以便观察并发效果
                execution_times.append(asyncio.get_event_loop().time() - task_start)
                return task_id

            results = await asyncio.gather(
                *[scheduler.submit(sample_task(i)) for i in range(4)]
            )

            # 验证结果正确性
            self.assertEqual(len(results), 4)
            self.assertEqual(set(results), {0, 1, 2, 3})

            # 验证并发限制是否生效
            total_time = asyncio.get_event_loop().time() - start_time
            self.assertGreater(
                total_time, 0.2
            )  # 由于max_concurrency=2，至少需要两轮执行

        self.loop.run_until_complete(test_scheduler())

    def test_error_handling(self):
        async def test_error():
            scheduler = AdaptiveAsyncConcurrencyLimiter(max_concurrency=2)

            async def failing_task():
                raise ValueError("测试错误")

            with self.assertRaises(ValueError):
                await scheduler.submit(failing_task())

        self.loop.run_until_complete(test_error())


if __name__ == "__main__":
    unittest.main()
