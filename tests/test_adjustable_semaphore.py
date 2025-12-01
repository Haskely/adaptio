import asyncio
import threading
import unittest
import warnings

from adaptio import (
    AdjustableSemaphore,
    AdjustableSemaphoreType,
    LoopLocalAdjustableSemaphore,
)


class TestAdjustableSemaphore(unittest.TestCase):
    def __init__(self, *args: str, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.loop: asyncio.AbstractEventLoop

    def setUp(self) -> None:
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

        async def internal_task(sem: AdjustableSemaphoreType) -> bool:
            nonlocal sem_acquire_count
            async with sem:
                sem_acquire_count += 1
                await asyncio.sleep(0.01)
                return True

        async def run_tasks(sem: AdjustableSemaphoreType) -> tuple[bool, bool]:
            return await asyncio.gather(internal_task(sem), internal_task(sem))  # type: ignore[return-value]

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
        async def task_without_ignore(sem: AdjustableSemaphoreType) -> bool:
            async with sem:
                await asyncio.sleep(0.01)
                return True

        async def run_tasks_without_ignore(
            sem: AdjustableSemaphoreType,
        ) -> tuple[bool, bool]:
            return await asyncio.gather(
                task_without_ignore(sem), task_without_ignore(sem)
            )  # type: ignore[return-value]

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
        async def task_with_ignore(sem: AdjustableSemaphoreType) -> bool:
            async with sem:
                await asyncio.sleep(0.01)
                return True

        async def run_tasks_with_ignore(
            sem: AdjustableSemaphoreType,
        ) -> tuple[bool, bool]:
            return await asyncio.gather(task_with_ignore(sem), task_with_ignore(sem))  # type: ignore[return-value]

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

    def test_multi_threading_with_loop_local(self):
        """测试 LoopLocalAdjustableSemaphore 在多线程多loop场景下的行为

        使用 LoopLocalAdjustableSemaphore 可以完美解决多线程场景下的问题：
        - 每个 event loop 拥有独立的 AdjustableSemaphore 实例
        - 不同 loop 之间互不干扰，各自独立计数和通知
        - 所有线程都能正常获取和释放信号量
        """
        # 使用新的 LoopLocalAdjustableSemaphore
        sem = LoopLocalAdjustableSemaphore(initial_value=2)

        results: list[str] = []
        errors: list[tuple[str, Exception]] = []

        def run_in_thread(thread_name: str):
            """在新线程中运行异步任务"""

            async def worker():
                try:
                    async with sem:
                        results.append(f"{thread_name} acquired")
                        await asyncio.sleep(0.1)
                        results.append(f"{thread_name} released")
                        return True
                except Exception as e:
                    errors.append((thread_name, e))
                    return False

            # 在新的 event loop 中运行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = loop.run_until_complete(worker())
                    return result
            finally:
                loop.close()

        # 创建多个线程，每个线程有自己的 event loop
        threads = []
        for i in range(4):
            t = threading.Thread(target=run_in_thread, args=(f"Thread-{i}",))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join(timeout=5.0)
            self.assertFalse(
                t.is_alive(), f"Thread {t.name} is still alive (deadlocked)"
            )

        # 验证没有错误发生
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # 验证所有线程都成功获取和释放了信号量
        self.assertEqual(
            len(results), 8
        )  # 4 threads * 2 operations (acquire + release)

        # 验证每个线程都有 acquired 和 released
        for i in range(4):
            self.assertIn(f"Thread-{i} acquired", results)
            self.assertIn(f"Thread-{i} released", results)

    def test_loop_local_semaphore_basic_functionality(self):
        """测试 LoopLocalAdjustableSemaphore 的基本功能"""

        async def test_basic():
            sem = LoopLocalAdjustableSemaphore(initial_value=2)

            async def task():
                async with sem:
                    await asyncio.sleep(0.1)
                    return True

            # 测试基本的并发控制
            results = await asyncio.gather(*[task() for _ in range(3)])
            self.assertTrue(all(results))

            # 测试 get_value
            self.assertEqual(sem.get_value(), 2)

            # 测试 get_initial_value
            self.assertEqual(sem.get_initial_value_config(), 2)

        self.loop.run_until_complete(test_basic())

    def test_loop_local_semaphore_set_value(self):
        """测试 LoopLocalAdjustableSemaphore 的 set_value 功能"""

        async def test_set_value():
            sem = LoopLocalAdjustableSemaphore(initial_value=2)

            # 测试增加值
            await sem.set_value(4)
            self.assertEqual(sem.get_value(), 4)

            # 测试减少值
            await sem.set_value(1)
            self.assertEqual(sem.get_value(), 1)

            async def task():
                async with sem:
                    await asyncio.sleep(0.1)
                    return True

            # 创建任务，只有一个能立即执行
            tasks = [asyncio.create_task(task()) for _ in range(2)]
            done, pending = await asyncio.wait(tasks, timeout=0.15)
            self.assertEqual(len(done), 1)
            self.assertEqual(len(pending), 1)

            # 清理
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        self.loop.run_until_complete(test_set_value())

    def test_loop_local_semaphore_multiple_asyncio_run(self):
        """测试 LoopLocalAdjustableSemaphore 在多次 asyncio.run() 调用间的行为"""

        async def use_sem(sem: AdjustableSemaphoreType, worker_id: int):
            # 每次调用都使用独立的 loop，因此有独立的信号量实例
            async with sem:
                await asyncio.sleep(0.01)
                return worker_id

        # 创建一个 LoopLocalAdjustableSemaphore
        sem = LoopLocalAdjustableSemaphore(initial_value=1)

        # 多次 asyncio.run() 都应该成功（每次使用不同 loop 的独立信号量）
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result1 = asyncio.run(use_sem(sem, 1))
            self.assertEqual(result1, 1)

            result2 = asyncio.run(use_sem(sem, 2))
            self.assertEqual(result2, 2)

            result3 = asyncio.run(use_sem(sem, 3))
            self.assertEqual(result3, 3)

    def test_asyncio_run_multiple_times_with_loop_local_should_succeed(self):
        """测试 LoopLocalCondition 在多次 asyncio.run() 调用间能正常工作"""

        async def create_and_use_sem():
            # 在第一个 loop 中创建并使用 semaphore
            sem = AdjustableSemaphore(initial_value=1, ignore_loop_bound_exception=True)
            async with sem:
                await asyncio.sleep(0.01)
            return sem

        # 第一次 asyncio.run() - 创建并使用 semaphore
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sem = asyncio.run(create_and_use_sem())

        async def use_existing_sem(worker_id: int):
            # 在后续的 loop 中使用 semaphore - 应该使用各自 loop 的 Condition
            async with sem:
                await asyncio.sleep(0.01)
                return worker_id

        # 多次 asyncio.run() 都应该成功（因为使用 LoopLocalCondition）
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result1 = asyncio.run(use_existing_sem(1))
            self.assertEqual(result1, 1)

            result2 = asyncio.run(use_existing_sem(2))
            self.assertEqual(result2, 2)

            result3 = asyncio.run(use_existing_sem(3))
            self.assertEqual(result3, 3)

    def test_loop_local_semaphore_concurrent_limit_integration(self):
        """集成测试：验证 LoopLocalAdjustableSemaphore 能够正确限制并发数

        这个测试模拟真实场景，验证：
        1. 实际运行的并发数能够接近（但不超过）设定的限制
        2. 动态调整并发限制后，系统能够正确响应
        """
        import random

        # 并发阈值和计数器
        max_allowed_concurrent = 10
        current_running = 0
        max_running_observed = 0
        overload_count = 0
        total_tasks = 0

        async def monitored_task(sem: LoopLocalAdjustableSemaphore, task_id: int):
            """模拟任务，监控并发数"""
            nonlocal current_running, max_running_observed, overload_count, total_tasks

            async with sem:
                current_running += 1
                total_tasks += 1

                # 记录观察到的最大并发数
                if current_running > max_running_observed:
                    max_running_observed = current_running

                # 检测是否超过阈值
                if current_running > max_allowed_concurrent:
                    overload_count += 1
                    # 只记录前几次过载
                    if overload_count <= 3:
                        print(
                            f"⚠️ 过载检测: 当前并发 {current_running} > 限制 {max_allowed_concurrent}"
                        )

                # 模拟任务执行时间
                await asyncio.sleep(random.uniform(0.01, 0.05))
                current_running -= 1

                return f"Task {task_id} done"

        async def run_integration_test():
            nonlocal \
                current_running, \
                max_running_observed, \
                overload_count, \
                max_allowed_concurrent

            # 创建信号量，初始值为 5
            sem = LoopLocalAdjustableSemaphore(initial_value=5)

            print("\n=== 阶段 1: 初始并发限制为 5 ===")
            max_allowed_concurrent = 5
            current_running = 0
            max_running_observed = 0
            overload_count = 0

            # 启动 30 个任务
            tasks = [monitored_task(sem, i) for i in range(30)]
            await asyncio.gather(*tasks)

            print(
                f"✓ 完成阶段 1: 最大观察并发={max_running_observed}, 过载次数={overload_count}"
            )
            # 验证：最大并发应该接近 5，允许小幅超出（由于竞态条件）
            self.assertLessEqual(
                max_running_observed,
                7,
                f"并发数 {max_running_observed} 超出限制 5 太多",
            )
            self.assertGreaterEqual(
                max_running_observed,
                4,
                f"并发数 {max_running_observed} 未充分利用限制 5",
            )

            # 阶段 2: 提升并发限制到 10
            print("\n=== 阶段 2: 提升并发限制到 10 ===")
            max_allowed_concurrent = 10
            current_running = 0
            max_running_observed = 0
            overload_count = 0

            await sem.set_value(10)

            # 启动 50 个任务
            tasks = [monitored_task(sem, i + 100) for i in range(50)]
            await asyncio.gather(*tasks)

            print(
                f"✓ 完成阶段 2: 最大观察并发={max_running_observed}, 过载次数={overload_count}"
            )
            # 验证：最大并发应该接近 10
            self.assertLessEqual(
                max_running_observed,
                12,
                f"并发数 {max_running_observed} 超出限制 10 太多",
            )
            self.assertGreaterEqual(
                max_running_observed,
                8,
                f"并发数 {max_running_observed} 未充分利用限制 10",
            )

            # 阶段 3: 降低并发限制到 3
            print("\n=== 阶段 3: 降低并发限制到 3 ===")
            max_allowed_concurrent = 3
            current_running = 0
            max_running_observed = 0
            overload_count = 0

            await sem.set_value(3)

            # 启动 20 个任务
            tasks = [monitored_task(sem, i + 200) for i in range(20)]
            await asyncio.gather(*tasks)

            print(
                f"✓ 完成阶段 3: 最大观察并发={max_running_observed}, 过载次数={overload_count}"
            )
            # 验证：最大并发应该接近 3
            self.assertLessEqual(
                max_running_observed,
                5,
                f"并发数 {max_running_observed} 超出限制 3 太多",
            )
            self.assertGreaterEqual(
                max_running_observed,
                2,
                f"并发数 {max_running_observed} 未充分利用限制 3",
            )

            print(f"\n✅ 集成测试通过！总任务数: {total_tasks}")

        self.loop.run_until_complete(run_integration_test())


if __name__ == "__main__":
    unittest.main()
