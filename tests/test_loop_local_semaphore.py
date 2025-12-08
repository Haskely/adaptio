import asyncio
import threading
from typing import Any

import pytest

from adaptio.loop_local_semaphore import LoopLocalSemaphore


class TestLoopLocalSemaphore:
    """测试 LoopLocalSemaphore 的基本功能"""

    @pytest.mark.asyncio
    async def test_basic_acquire_release(self):
        """测试基本的 acquire 和 release 功能"""
        sem = LoopLocalSemaphore(2)

        # 第一次 acquire
        assert await sem.acquire() is True
        assert not sem.locked()  # 还有一个可用

        # 第二次 acquire
        assert await sem.acquire() is True
        assert sem.locked()  # 现在已满

        # Release 一次
        sem.release()
        assert not sem.locked()

        # Release 第二次
        sem.release()
        assert not sem.locked()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试 async with 语法"""
        sem = LoopLocalSemaphore(1)
        counter = 0

        async def worker():
            nonlocal counter
            async with sem:
                await asyncio.sleep(0.01)
                counter += 1

        # 启动多个任务
        await asyncio.gather(*[worker() for _ in range(5)])
        assert counter == 5

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """测试并发限制是否生效"""
        sem = LoopLocalSemaphore(2)
        concurrent_count = 0
        max_concurrent = 0

        async def worker():
            nonlocal concurrent_count, max_concurrent
            async with sem:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.05)
                concurrent_count -= 1

        # 启动 10 个任务
        await asyncio.gather(*[worker() for _ in range(10)])

        # 验证最大并发数不超过 2
        assert max_concurrent == 2
        assert concurrent_count == 0

    @pytest.mark.asyncio
    async def test_different_loops_independent(self):
        """测试不同 event loop 之间的 semaphore 是独立的"""
        sem = LoopLocalSemaphore(1)
        results: dict[str, Any] = {}

        async def task_in_loop(loop_id: str):
            """在当前 loop 中运行的任务"""
            async with sem:
                results[loop_id] = "acquired"
                await asyncio.sleep(0.01)

        # 在当前 loop 中运行
        await task_in_loop("loop1")
        assert "loop1" in results

        # 在新线程的新 loop 中运行
        def run_in_new_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(task_in_loop("loop2"))
            finally:
                loop.close()

        thread = threading.Thread(target=run_in_new_loop)
        thread.start()
        thread.join()

        # 验证两个 loop 都成功获取了各自的 semaphore
        assert "loop2" in results

    @pytest.mark.asyncio
    async def test_invalid_initial_value(self):
        """测试负数初始值会抛出异常"""
        with pytest.raises(ValueError, match="Semaphore initial value must be >= 0"):
            LoopLocalSemaphore(-1)

    @pytest.mark.asyncio
    async def test_zero_initial_value(self):
        """测试初始值为 0 的情况"""
        sem = LoopLocalSemaphore(0)
        assert sem.locked()

        # 创建一个等待 acquire 的任务
        acquired = False

        async def try_acquire():
            nonlocal acquired
            await sem.acquire()
            acquired = True

        task = asyncio.create_task(try_acquire())

        # 等待一小段时间，确保任务开始等待
        await asyncio.sleep(0.01)
        assert not acquired  # 应该还在等待

        # Release 后应该能获取
        sem.release()
        await task
        assert acquired

    @pytest.mark.asyncio
    async def test_multiple_releases_exceed_initial(self):
        """测试 release 次数超过 acquire 次数（与 asyncio.Semaphore 行为一致）"""
        sem = LoopLocalSemaphore(1)

        # 正常 acquire 和 release
        await sem.acquire()
        sem.release()

        # 额外 release（这在 asyncio.Semaphore 中是允许的）
        sem.release()

        # 现在应该可以 acquire 两次而不阻塞
        await sem.acquire()
        await sem.acquire()

    def test_outside_event_loop_raises_error(self):
        """测试在没有运行 event loop 的情况下调用会抛出异常"""
        sem = LoopLocalSemaphore(1)

        with pytest.raises(
            RuntimeError, match="must be used inside an asyncio event loop"
        ):
            sem.locked()

    @pytest.mark.asyncio
    async def test_with_async_control_integration(self):
        """测试与 with_async_control 的集成"""
        from adaptio.with_async_control import with_async_control

        execution_order: list[str] = []
        sem = LoopLocalSemaphore(2)

        @with_async_control(max_concurrency=2, ignore_loop_bound_exception=True)
        async def worker(task_id: int):
            async with sem:
                execution_order.append(f"start-{task_id}")
                await asyncio.sleep(0.01)
                execution_order.append(f"end-{task_id}")

        # 启动多个任务
        await asyncio.gather(*[worker(i) for i in range(5)])

        # 验证所有任务都完成了
        start_items = [x for x in execution_order if x.startswith("start")]
        end_items = [x for x in execution_order if x.startswith("end")]
        assert len(start_items) == 5
        assert len(end_items) == 5
