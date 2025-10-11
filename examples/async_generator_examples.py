"""
异步生成器装饰器使用示例

展示如何使用 with_adaptive_retry 装饰器来处理异步生成器函数。
"""

import asyncio

from adaptio import ServiceOverloadError, with_adaptive_retry


# 示例 1：基础用法
@with_adaptive_retry()
async def basic_generator():
    """最简单的用法 - 生成一系列数字"""
    for i in range(10):
        await asyncio.sleep(0.1)
        yield i


# 示例 2：处理 API 限流
@with_adaptive_retry(initial_concurrency=5, max_retries=10, retry_interval_seconds=2)
async def fetch_with_rate_limit(base_url: str, total_pages: int):
    """模拟有限流的 API 调用"""
    import random

    for page in range(1, total_pages + 1):
        # 模拟随机限流 (30% 概率)
        if random.random() < 0.3:
            raise ServiceOverloadError(f"Page {page} rate limited")

        # 模拟获取数据
        await asyncio.sleep(0.5)
        yield f"Data from page {page}"


# 示例 3：分页数据爬取
@with_adaptive_retry(initial_concurrency=3, max_concurrency=10)
async def crawl_paginated_data(endpoint: str, max_pages: int = 100):
    """模拟分页 API 爬取"""
    page = 1
    while page <= max_pages:
        # 模拟 API 请求
        await asyncio.sleep(0.3)

        # 模拟偶尔的服务器错误
        import random

        if random.random() < 0.1:
            raise ServiceOverloadError(f"Server overloaded at page {page}")

        # 模拟返回数据
        items = [f"{endpoint}/item-{page}-{i}" for i in range(1, 4)]

        for item in items:
            yield item

        page += 1

        # 模拟最后一页没有数据
        if page > max_pages:
            break


# 示例 4：批量数据处理
@with_adaptive_retry(initial_concurrency=2)
async def process_batch_data(data_source: str, batch_size: int = 10):
    """模拟批量数据处理"""
    total_items = 50

    for batch_start in range(0, total_items, batch_size):
        batch_end = min(batch_start + batch_size, total_items)

        # 模拟批量获取数据
        await asyncio.sleep(0.5)

        # 模拟处理每个批次的数据
        for item_id in range(batch_start, batch_end):
            yield {"id": item_id, "data": f"Item {item_id} from {data_source}"}


# 示例 5：多生成器并发运行
async def multiple_generators_example():
    """演示多个生成器并发运行"""

    @with_adaptive_retry(initial_concurrency=3)
    async def worker_generator(worker_id: int, task_count: int):
        for task_id in range(task_count):
            await asyncio.sleep(0.5)
            yield f"Worker-{worker_id}-Task-{task_id}"

    # 创建多个生成器
    workers = [worker_generator(i, 5) for i in range(3)]

    # 并发消费
    async def consume(gen, name: str) -> list[str]:
        results: list[str] = []
        async for item in gen:
            print(f"{name}: {item}")
            results.append(item)  # type: ignore[arg-type]
        return results

    all_results = await asyncio.gather(
        *[consume(gen, f"Consumer-{i}") for i, gen in enumerate(workers)]
    )  # type: ignore[arg-type]

    print(f"\n总共收集了 {sum(len(r) for r in all_results)} 个项目")  # type: ignore[arg-type]


# 示例 6：带错误处理的生成器
@with_adaptive_retry(max_retries=5)
async def resilient_generator(source: str):
    """展示错误处理和重试机制"""
    import random

    items_produced = 0

    for i in range(10):
        # 模拟可能失败的操作（降低失败概率）
        if random.random() < 0.15:
            print(f"[{source}] 遇到临时错误，将重试...")
            raise ServiceOverloadError(f"Temporary error at item {i}")

        await asyncio.sleep(0.2)
        items_produced += 1
        yield f"{source}-item-{i}"

    print(f"[{source}] 成功产出 {items_produced} 个项目")


# 主函数：运行所有示例
async def main():
    print("=" * 60)
    print("示例 1: 基础生成器用法")
    print("=" * 60)
    async for item in basic_generator():
        print(f"收到: {item}")

    print("\n" + "=" * 60)
    print("示例 2: 处理 API 限流")
    print("=" * 60)
    async for data in fetch_with_rate_limit("https://api.example.com", 5):
        print(f"收到: {data}")

    print("\n" + "=" * 60)
    print("示例 3: 分页数据爬取")
    print("=" * 60)
    count = 0
    async for item in crawl_paginated_data("https://api.example.com/users", 3):
        count += 1
        if count <= 10:  # 只打印前10个
            print(f"收到: {item}")
    print(f"总共爬取 {count} 个项目")

    print("\n" + "=" * 60)
    print("示例 4: 批量数据处理")
    print("=" * 60)
    count = 0
    async for item in process_batch_data("database", batch_size=15):
        count += 1
        if count <= 10:  # 只打印前10个
            print(f"处理: {item}")
    print(f"总共处理 {count} 个项目")

    print("\n" + "=" * 60)
    print("示例 5: 多生成器并发运行")
    print("=" * 60)
    await multiple_generators_example()

    print("\n" + "=" * 60)
    print("示例 6: 带错误处理的生成器")
    print("=" * 60)
    results: list[str] = []
    async for item in resilient_generator("source-A"):
        results.append(item)  # type: ignore[arg-type]
        print(f"收到: {item}")
    print(f"最终收集了 {len(results)} 个项目")


if __name__ == "__main__":
    print("异步生成器装饰器使用示例\n")
    asyncio.run(main())
