"""
LoopLocalSemaphore 使用示例

演示如何使用 LoopLocalSemaphore 来实现多线程/多 event loop 场景下的并发控制。
"""

import asyncio
import threading
import time
from typing import Any

from adaptio import LoopLocalSemaphore


def example_basic_usage():
    """示例 1: 基本使用 - 限制并发数"""
    print("=" * 60)
    print("示例 1: 基本使用 - 使用 LoopLocalSemaphore 限制并发数")
    print("=" * 60)

    # 创建一个允许最多 3 个并发的信号量
    sem = LoopLocalSemaphore(3)

    async def worker(task_id: int):
        print(f"任务 {task_id} 正在等待获取信号量...")
        async with sem:
            print(f"  → 任务 {task_id} 获得信号量，开始执行")
            await asyncio.sleep(1)
            print(f"  ← 任务 {task_id} 完成")

    async def main():
        # 启动 10 个任务，但同时最多只有 3 个在执行
        await asyncio.gather(*[worker(i) for i in range(10)])

    asyncio.run(main())
    print()


def example_multi_loop():
    """示例 2: 多 event loop 场景 - 每个 loop 有独立的信号量"""
    print("=" * 60)
    print("示例 2: 多 event loop - 每个 loop 独立的并发控制")
    print("=" * 60)

    # 同一个 LoopLocalSemaphore 实例
    sem = LoopLocalSemaphore(2)
    results: dict[str, Any] = {}

    async def worker_in_loop(loop_name: str, task_id: int):
        async with sem:
            msg = f"{loop_name} - 任务 {task_id} 执行中"
            print(f"  → {msg}")
            await asyncio.sleep(0.5)
            results[f"{loop_name}-{task_id}"] = "completed"
            print(f"  ← {loop_name} - 任务 {task_id} 完成")

    def run_in_loop(loop_name: str, num_tasks: int):
        """在独立的 event loop 中运行任务"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            print(f"\n{loop_name} 启动，运行 {num_tasks} 个任务...")
            tasks = [worker_in_loop(loop_name, i) for i in range(num_tasks)]
            loop.run_until_complete(asyncio.gather(*tasks))
            print(f"{loop_name} 完成")
        finally:
            loop.close()

    # 在不同线程中运行不同的 event loop
    # 每个 loop 都会有自己独立的信号量实例（最多 2 个并发）
    threads = [
        threading.Thread(target=run_in_loop, args=(f"Loop-{i}", 5)) for i in range(3)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    print(f"\n总共完成了 {len(results)} 个任务")
    print()


def example_with_async_control_integration():
    """示例 3: 与 with_async_control 集成"""
    print("=" * 60)
    print("示例 3: 与 with_async_control 集成使用")
    print("=" * 60)

    from adaptio import with_async_control

    @with_async_control(
        max_concurrency=3,
        max_qps=5,
        retry_n=2,
        ignore_loop_bound_exception=True,  # 使用 LoopLocalSemaphore
    )
    async def fetch_data(url: str) -> str:
        """模拟 API 调用"""
        print(f"  → 获取数据: {url}")
        await asyncio.sleep(0.5)
        return f"数据: {url}"

    async def main():
        urls = [f"https://api.example.com/data/{i}" for i in range(10)]

        start_time = time.time()
        results = await asyncio.gather(*[fetch_data(url) for url in urls])
        elapsed = time.time() - start_time

        print(f"\n完成 {len(results)} 个请求，耗时: {elapsed:.2f}秒")
        print(f"平均每个请求: {elapsed / len(results):.2f}秒")

    asyncio.run(main())
    print()


def example_manual_acquire_release():
    """示例 4: 手动控制 acquire 和 release"""
    print("=" * 60)
    print("示例 4: 手动控制 acquire/release")
    print("=" * 60)

    sem = LoopLocalSemaphore(2)

    async def worker(task_id: int):
        print(f"任务 {task_id} 尝试获取信号量...")
        await sem.acquire()
        try:
            print(f"  → 任务 {task_id} 获得信号量")
            print(f"     信号量是否已锁定: {sem.locked()}")
            await asyncio.sleep(1)
        finally:
            sem.release()
            print(f"  ← 任务 {task_id} 释放信号量")

    async def main():
        await asyncio.gather(*[worker(i) for i in range(5)])

    asyncio.run(main())
    print()


def example_compare_with_standard_semaphore():
    """示例 5: 对比标准 Semaphore 的多线程问题"""
    print("=" * 60)
    print("示例 5: 对比标准 Semaphore 在多线程场景的问题")
    print("=" * 60)

    # 使用标准 asyncio.Semaphore
    standard_sem = asyncio.Semaphore(2)

    async def worker_standard(task_id: int):
        try:
            async with standard_sem:
                print(f"  标准 Semaphore - 任务 {task_id} 执行")
                await asyncio.sleep(0.1)
        except RuntimeError as e:
            print(f"  ❌ 标准 Semaphore - 任务 {task_id} 失败: {e}")

    def run_with_standard_semaphore():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tasks = [worker_standard(i) for i in range(3)]
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        finally:
            loop.close()

    print("\n尝试在新线程中使用标准 asyncio.Semaphore:")
    thread = threading.Thread(target=run_with_standard_semaphore)
    thread.start()
    thread.join()

    # 使用 LoopLocalSemaphore
    loop_local_sem = LoopLocalSemaphore(2)

    async def worker_loop_local(task_id: int):
        async with loop_local_sem:
            print(f"  ✓ LoopLocal Semaphore - 任务 {task_id} 执行")
            await asyncio.sleep(0.1)

    def run_with_loop_local_semaphore():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tasks = [worker_loop_local(i) for i in range(3)]
            loop.run_until_complete(asyncio.gather(*tasks))
        finally:
            loop.close()

    print("\n使用 LoopLocalSemaphore (支持多线程):")
    thread = threading.Thread(target=run_with_loop_local_semaphore)
    thread.start()
    thread.join()
    print()


if __name__ == "__main__":
    # 运行所有示例
    example_basic_usage()
    example_multi_loop()
    example_with_async_control_integration()
    example_manual_acquire_release()
    example_compare_with_standard_semaphore()

    print("=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
