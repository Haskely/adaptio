import asyncio
import unittest

from adaptio import AdjustableSemaphore


class TestAdjustableSemaphore(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_basic_semaphore_functionality(self):
        async def test_sem():
            sem = AdjustableSemaphore(initial_value=2)

            async def task():
                async with sem:
                    await asyncio.sleep(0.1)
                    return True

            results = await asyncio.gather(*[task() for _ in range(3)])
            self.assertTrue(all(results))
            self.assertEqual(sem.get_value(), 2)

        self.loop.run_until_complete(test_sem())

    def test_adjust_value(self):
        async def test_sem():
            sem = AdjustableSemaphore(initial_value=2)
            self.assertEqual(sem.get_value(), 2)

            # 测试增加值
            await sem.set_value(4)
            self.assertEqual(sem.get_value(), 4)

            # 测试减少值
            await sem.set_value(1)
            self.assertEqual(sem.get_value(), 1)

            async def task() -> bool:
                async with sem:
                    await asyncio.sleep(0.1)
                    return True

            # 创建任务而不是直接使用协程
            tasks = [asyncio.create_task(task()) for _ in range(2)]
            done, pending = await asyncio.wait(tasks, timeout=0.15)
            self.assertEqual(len(done), 1)  # 只有一个任务应该完成
            self.assertEqual(len(pending), 1)  # 一个任务应该还在等待

            # 清理剩余的任务
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        self.loop.run_until_complete(test_sem())

    def test_invalid_values(self):
        async def test_sem():
            sem = AdjustableSemaphore(initial_value=1)

            # 测试设置无效值
            with self.assertRaises(ValueError):
                await sem.set_value(-1)

        self.loop.run_until_complete(test_sem())


if __name__ == "__main__":
    unittest.main()
