"""
LoopLocalAdjustableSemaphore 使用示例

这个示例展示了如何在多线程场景下使用 LoopLocalAdjustableSemaphore。
每个线程都有自己的 event loop 和独立的信号量实例。
"""

import asyncio
import threading
import time

from adaptio import LoopLocalAdjustableSemaphore


def example_1_multi_threading():
    """示例1: 多线程场景，每个线程有独立的并发控制"""
    print("\n=== 示例1: 多线程场景 ===")

    # 创建一个 loop-local 信号量，每个线程限制 2 个并发
    sem = LoopLocalAdjustableSemaphore(initial_value=2)

    def run_in_thread(thread_name: str):
        async def worker(task_id: int):
            async with sem:
                print(f"[{thread_name}] Task-{task_id} 开始执行")
                await asyncio.sleep(0.5)
                print(f"[{thread_name}] Task-{task_id} 执行完成")
                return f"{thread_name}-Task-{task_id}"

        async def main():
            # 每个线程创建 5 个任务，但最多同时执行 2 个
            tasks = [worker(i) for i in range(5)]
            results = await asyncio.gather(*tasks)
            print(f"[{thread_name}] 所有任务完成: {results}")

        asyncio.run(main())

    # 启动 3 个线程
    threads = []
    for i in range(3):
        t = threading.Thread(target=run_in_thread, args=(f"Thread-{i}",))
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    print("所有线程已完成\n")


def example_2_dynamic_adjustment():
    """示例2: 动态调整并发数"""
    print("\n=== 示例2: 动态调整并发数 ===")

    sem = LoopLocalAdjustableSemaphore(initial_value=5)

    async def worker(task_id: int):
        async with sem:
            current_value = sem.get_value()
            print(f"Task-{task_id} 开始执行 (可用信号量: {current_value})")
            await asyncio.sleep(0.2)
            print(f"Task-{task_id} 执行完成")
            return task_id

    async def controller():
        """动态调整并发数的控制器"""
        await asyncio.sleep(0.3)
        print("\n>>> 将并发数从 5 调整为 2")
        await sem.set_value(2)

        await asyncio.sleep(0.5)
        print("\n>>> 将并发数从 2 调整为 10")
        await sem.set_value(10)
        return 0  # 返回一个值以匹配类型

    async def main():
        # 创建 15 个任务
        tasks = [asyncio.create_task(worker(i)) for i in range(15)]

        # 启动控制器
        controller_task = asyncio.create_task(controller())

        # 等待所有任务完成
        await asyncio.gather(*tasks, controller_task)
        print("\n所有任务完成")

    asyncio.run(main())


def example_3_multiple_asyncio_run():
    """示例3: 多次调用 asyncio.run()"""
    print("\n=== 示例3: 多次调用 asyncio.run() ===")

    # 创建一个 loop-local 信号量
    sem = LoopLocalAdjustableSemaphore(initial_value=1)

    async def process(batch_id: int):
        print(f"开始处理批次 {batch_id}")
        async with sem:
            print(f"  批次 {batch_id} 获取了信号量")
            await asyncio.sleep(0.1)
            print(f"  批次 {batch_id} 处理完成")
        return batch_id

    # 多次调用 asyncio.run()，每次都会使用新的 loop
    for i in range(5):
        result = asyncio.run(process(i))
        print(f"批次 {result} 返回结果\n")

    print("所有批次处理完成\n")


def example_4_mixed_scenario():
    """示例4: 混合场景 - 同时演示单线程和多线程"""
    print("\n=== 示例4: 混合场景 ===")

    sem = LoopLocalAdjustableSemaphore(initial_value=3)

    async def async_worker(worker_id: int, loop_name: str):
        async with sem:
            print(f"[{loop_name}] Worker-{worker_id} 开始")
            await asyncio.sleep(0.2)
            print(f"[{loop_name}] Worker-{worker_id} 完成")
            return worker_id

    def thread_worker(thread_name: str):
        """在独立线程中运行多个异步任务"""

        async def main():
            tasks = [async_worker(i, thread_name) for i in range(6)]
            results = await asyncio.gather(*tasks)
            print(f"[{thread_name}] 完成任务: {results}")

        asyncio.run(main())

    # 先在主线程中运行一些任务
    print("主线程开始执行...")

    async def main_thread_tasks():
        tasks = [async_worker(i, "MainThread") for i in range(4)]
        await asyncio.gather(*tasks)

    asyncio.run(main_thread_tasks())

    # 然后在多个子线程中运行
    print("\n启动子线程...")
    threads = []
    for i in range(2):
        t = threading.Thread(target=thread_worker, args=(f"SubThread-{i}",))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("\n混合场景执行完成")


def example_5_error_handling():
    """示例5: 错误处理"""
    print("\n=== 示例5: 错误处理 ===")

    sem = LoopLocalAdjustableSemaphore(initial_value=2)

    async def worker_with_error(task_id: int, should_fail: bool):
        async with sem:
            print(f"Task-{task_id} 开始执行")
            await asyncio.sleep(0.1)
            if should_fail:
                print(f"Task-{task_id} 抛出异常")
                raise ValueError(f"Task {task_id} failed")
            print(f"Task-{task_id} 成功完成")
            return task_id

    async def main():
        tasks = [
            asyncio.create_task(worker_with_error(i, i % 3 == 0)) for i in range(6)
        ]

        # 收集结果，包括异常
        results = await asyncio.gather(*tasks, return_exceptions=True)

        print("\n结果汇总:")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"  Task-{i}: 失败 - {result}")
            else:
                print(f"  Task-{i}: 成功 - 返回值 {result}")

    asyncio.run(main())


if __name__ == "__main__":
    # 运行所有示例
    example_1_multi_threading()
    time.sleep(0.5)

    example_2_dynamic_adjustment()
    time.sleep(0.5)

    example_3_multiple_asyncio_run()
    time.sleep(0.5)

    example_4_mixed_scenario()
    time.sleep(0.5)

    example_5_error_handling()

    print("\n所有示例执行完成！")
