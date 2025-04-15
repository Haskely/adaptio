import asyncio
import unittest
import warnings

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

    def test_semaphore_across_event_loops(self):
        """测试在多次调用asyncio.run()之间重用信号量的行为"""

        # 1. 测试默认行为（不忽略循环绑定异常）
        # 使用函数内的变量来跟踪每个测试阶段

        sem_acquire_count = 0

        async def internal_task(sem):
            nonlocal sem_acquire_count
            async with sem:
                sem_acquire_count += 1
                await asyncio.sleep(0.01)
                return True

        async def run_tasks(sem):
            return await asyncio.gather(internal_task(sem), internal_task(sem))

        # 创建一个没有忽略循环绑定异常的信号量
        sem_no_ignore = AdjustableSemaphore(initial_value=1)

        # 第一次运行应该正常完成，两个任务都能获取信号量
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = asyncio.run(run_tasks(sem_no_ignore))
            self.assertEqual(len(results), 2)
            self.assertTrue(all(results))
            self.assertEqual(sem_acquire_count, 2)

        # 重置计数器
        sem_acquire_count = 0

        # 第二次运行应该抛出RuntimeError，因为信号量绑定到了不同的事件循环
        with self.assertRaises(RuntimeError), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            asyncio.run(run_tasks(sem_no_ignore))

        # 2. 测试ignore_loop_bound_exception=True的行为
        sem_acquire_count = 0

        # 创建一个忽略循环绑定异常的信号量
        sem_ignore = AdjustableSemaphore(
            initial_value=1, ignore_loop_bound_exception=True
        )

        # 第一次运行应该正常完成
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = asyncio.run(run_tasks(sem_ignore))
            self.assertEqual(len(results), 2)
            self.assertTrue(all(results))
            self.assertEqual(sem_acquire_count, 2)

        # 重置计数器
        sem_acquire_count = 0

        # 第二次运行不应抛出异常，但信号量不再限制并发
        # 两个任务应该能够几乎同时获取信号量
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = asyncio.run(run_tasks(sem_ignore))
            self.assertEqual(len(results), 2)
            self.assertTrue(all(results))
            self.assertEqual(sem_acquire_count, 2)

    def test_loop_bound_exception_with_contention(self):
        """更直接地测试多任务竞争时的循环绑定异常

        这个测试直接模拟dist/test.py中的情况，确保信号量进入等待状态
        从而触发循环绑定检查
        """

        # 第一个测试：确保在同一个循环内工作正常
        async def first_test():
            # 创建一个值为1的信号量
            sem = AdjustableSemaphore(initial_value=1)

            # 模拟两个并发任务竞争信号量
            async def task():
                async with sem:
                    await asyncio.sleep(0.01)
                    return True

            # 两个任务应该都能获取信号量并成功完成
            results = await asyncio.gather(task(), task())
            self.assertEqual(len(results), 2)
            self.assertTrue(all(results))

        self.loop.run_until_complete(first_test())

        # 第二个测试：测试跨不同循环的行为 - 不忽略异常
        async def task_without_ignore(sem):
            async with sem:
                await asyncio.sleep(0.01)
                return True

        async def run_tasks_without_ignore(sem):
            return await asyncio.gather(
                task_without_ignore(sem), task_without_ignore(sem)
            )

        # 创建一个没有忽略循环绑定异常的信号量
        sem_no_ignore = AdjustableSemaphore(initial_value=1)

        # 第一次运行应该正常
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = asyncio.run(run_tasks_without_ignore(sem_no_ignore))
            self.assertEqual(len(results), 2)
            self.assertTrue(all(results))

        # 第二次运行应该抛出RuntimeError - 循环绑定异常
        with self.assertRaises(RuntimeError), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            asyncio.run(run_tasks_without_ignore(sem_no_ignore))

        # 第三个测试：测试跨不同循环的行为 - 忽略异常
        async def task_with_ignore(sem):
            async with sem:
                await asyncio.sleep(0.01)
                return True

        async def run_tasks_with_ignore(sem):
            return await asyncio.gather(task_with_ignore(sem), task_with_ignore(sem))

        # 创建一个忽略循环绑定异常的信号量
        sem_ignore = AdjustableSemaphore(
            initial_value=1, ignore_loop_bound_exception=True
        )

        # 第一次运行应该正常
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = asyncio.run(run_tasks_with_ignore(sem_ignore))
            self.assertEqual(len(results), 2)
            self.assertTrue(all(results))

        # 第二次运行不应抛出异常但会有警告
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = asyncio.run(run_tasks_with_ignore(sem_ignore))
            self.assertEqual(len(results), 2)
            self.assertTrue(all(results))


if __name__ == "__main__":
    unittest.main()
