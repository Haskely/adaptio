"""集成测试：验证 with_adaptive_retry 装饰器的自适应并发控制功能

这个测试模拟真实场景，验证：
1. 系统能够检测到过载并降低并发数
2. 系统能够在运行正常时提升并发数
3. 并发数能够接近但不会长期超过过载阈值
"""

import asyncio
import logging
import random
import unittest

from adaptio import ServiceOverloadError, with_adaptive_retry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class TestWithAdaptiveRetryIntegration(unittest.TestCase):
    """with_adaptive_retry 装饰器的集成测试"""

    def test_adaptive_concurrency_with_overload_detection(self):
        """集成测试：验证自适应并发控制在过载场景下的行为

        测试场景：
        1. 设置过载阈值为 32 个并发任务
        2. 启动大量任务（200个）
        3. 验证系统能够：
           - 检测到过载（running_count > threshold）
           - 自动降低并发数
           - 在正常运行时提升并发数
           - 最终并发数稳定在阈值附近
        """
        # 过载阈值
        overload_threshold = 32

        # 统计数据
        stats: dict[str, list[int]] = {
            "running_count_samples": [],  # 运行时的并发数采样
            "overload_detections": [],  # 检测到过载时的并发数
            "max_running_count": [0],  # 观察到的最大并发数
        }

        # 当前运行任务数
        current_running = 0

        async def sample_task(task_id: int) -> str:
            """模拟任务：达到阈值后触发过载"""
            nonlocal current_running

            current_running += 1
            current_count = current_running

            # 记录当前并发数
            stats["running_count_samples"].append(current_count)

            # 更新最大并发数
            if current_count > stats["max_running_count"][0]:
                stats["max_running_count"][0] = current_count

            # 模拟随机任务耗时
            sleep_time = random.uniform(0.1, 0.3)

            # 检测过载
            if current_count > overload_threshold:
                stats["overload_detections"].append(current_count)
                current_running -= 1
                logging.warning(
                    f"❌ 过载检测: 当前并发={current_count} > 阈值={overload_threshold}"
                )
                raise ServiceOverloadError(
                    f"Service overloaded: {current_count} > {overload_threshold}"
                )

            # 正常执行
            await asyncio.sleep(sleep_time)
            current_running -= 1
            return f"Task {task_id} completed"

        # 使用 with_adaptive_retry 装饰器
        @with_adaptive_retry(
            initial_concurrency=4,
            max_concurrency=128,
            min_concurrency=1,
            adjust_overload_rate=0.1,
            log_level="INFO",
            log_prefix="adaptive_retry_test",
            ignore_loop_bound_exception=False,
        )
        async def sample_task_with_retry(task_id: int) -> str:
            return await sample_task(task_id)

        async def run_integration_test() -> list[str]:
            """运行集成测试"""
            # 创建大量任务
            tasks = [sample_task_with_retry(i) for i in range(200)]

            # 等待所有任务完成
            results: list[str] = []
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    results.append(result)
                except Exception as e:
                    logging.error(f"任务失败: {e}")

            return results

        # 运行测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(run_integration_test())
        finally:
            loop.close()

        # 验证结果
        print("\n" + "=" * 60)
        print("集成测试统计结果")
        print("=" * 60)

        # 1. 验证任务完成情况
        print(f"完成任务数: {len(results)} / 200")
        self.assertEqual(len(results), 200, "应该完成所有 200 个任务")

        # 2. 验证检测到过载
        overload_count = len(stats["overload_detections"])
        print(f"过载检测次数: {overload_count}")
        self.assertGreater(overload_count, 0, "应该检测到过载")

        # 3. 验证最大并发数
        max_running = stats["max_running_count"][0]
        print(f"最大并发数: {max_running}")
        print(f"过载阈值: {overload_threshold}")

        # 最大并发数应该接近阈值（允许略微超出）
        self.assertGreater(
            max_running,
            overload_threshold * 0.8,
            f"最大并发数 {max_running} 应该接近阈值 {overload_threshold}",
        )
        self.assertLess(
            max_running,
            overload_threshold * 1.5,
            f"最大并发数 {max_running} 不应该大幅超过阈值 {overload_threshold}",
        )

        # 4. 分析并发数分布
        samples = stats["running_count_samples"]
        avg_running = sum(samples) / len(samples)
        print(f"平均并发数: {avg_running:.2f}")

        # 计算在阈值附近的采样比例
        near_threshold = sum(
            1
            for x in samples
            if overload_threshold * 0.5 <= x <= overload_threshold * 1.2
        )
        near_threshold_ratio = near_threshold / len(samples)
        print(f"在阈值附近的采样比例: {near_threshold_ratio:.2%}")

        # 5. 验证过载后的并发数下降
        if len(stats["overload_detections"]) > 10:
            # 只有检测到足够多的过载才进行此验证
            overload_values = stats["overload_detections"]
            first_overloads = overload_values[:5]
            last_overloads = overload_values[-5:]

            avg_first = sum(first_overloads) / len(first_overloads)
            avg_last = sum(last_overloads) / len(last_overloads)

            print(f"初期过载时平均并发: {avg_first:.2f}")
            print(f"后期过载时平均并发: {avg_last:.2f}")

            # 后期过载时的并发数应该更接近阈值（说明系统在学习和优化）
            self.assertLessEqual(
                avg_last, avg_first * 1.1, "系统应该学会更精确地控制并发数"
            )

        print("=" * 60)
        print("✅ 集成测试通过！")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    unittest.main()
