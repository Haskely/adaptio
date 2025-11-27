import asyncio
import unittest
import warnings

from adaptio import with_async_control


class TestWithAsyncControl(unittest.TestCase):
    def __init__(self, *args: str, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.loop: asyncio.AbstractEventLoop

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_with_async_control(self):
        async def test_control():
            executed_tasks: list[int] = []

            @with_async_control(max_concurrency=2)
            async def controlled_task(task_id: int) -> int:
                executed_tasks.append(task_id)
                await asyncio.sleep(0.1)
                return task_id

            tasks = [controlled_task(i) for i in range(5)]
            results = await asyncio.gather(*tasks)  # type: ignore[arg-type]

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

    def test_asyncio_run_multiple_times_with_qps_and_loop_local(self):
        """测试 LoopLocalLock 在多次 asyncio.run() 调用间能正常工作"""

        @with_async_control(max_qps=10, ignore_loop_bound_exception=True)
        async def qps_controlled_task(task_id: int) -> str:
            return f"task-{task_id}"

        async def run_multiple_tasks(run_id: int):
            # 每次运行3个任务
            tasks = [qps_controlled_task(i) for i in range(3)]
            results = await asyncio.gather(*tasks)  # type: ignore[arg-type]
            return (run_id, results)

        # 多次 asyncio.run() 都应该成功（因为使用 LoopLocalLock）
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            run1_id, run1_results = asyncio.run(run_multiple_tasks(1))
            self.assertEqual(run1_id, 1)
            self.assertEqual(len(run1_results), 3)

            run2_id, run2_results = asyncio.run(run_multiple_tasks(2))
            self.assertEqual(run2_id, 2)
            self.assertEqual(len(run2_results), 3)

            run3_id, run3_results = asyncio.run(run_multiple_tasks(3))
            self.assertEqual(run3_id, 3)
            self.assertEqual(len(run3_results), 3)


if __name__ == "__main__":
    unittest.main()
