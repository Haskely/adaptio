"""演示 raise_on_overload 和 raise_on_aiohttp_overload 装饰器的统一使用方式。

这两个装饰器现在都支持：
1. 普通异步函数
2. 异步生成器

装饰器会自动检测函数类型，无需用户手动选择。
"""

import asyncio
from collections.abc import AsyncGenerator

import aiohttp

from adaptio import (
    ServiceOverloadError,
    raise_on_aiohttp_overload,
    raise_on_overload,
)


# ============================================================================
# 示例 1: raise_on_overload 装饰普通异步函数
# ============================================================================
@raise_on_overload()
async def fetch_data_with_exception_check(url: str) -> dict:
    """模拟一个可能抛出过载异常的API调用"""
    await asyncio.sleep(0.1)

    # 模拟服务过载
    if "overload" in url:
        raise ConnectionError("服务暂时 overload，请稍后重试")

    return {"url": url, "status": "success"}


# ============================================================================
# 示例 2: raise_on_overload 装饰异步生成器
# ============================================================================
@raise_on_overload()
async def fetch_pages_with_exception_check(base_url: str) -> AsyncGenerator[dict, None]:
    """模拟分页获取数据，可能在某些页面遇到过载错误"""
    for page in range(1, 6):
        await asyncio.sleep(0.1)

        # 模拟第3页遇到过载
        if page == 3:
            raise RuntimeError("too many requests - 请稍后重试")

        yield {"page": page, "url": f"{base_url}?page={page}", "data": f"数据_{page}"}


# ============================================================================
# 示例 3: raise_on_aiohttp_overload 装饰普通异步函数
# ============================================================================
@raise_on_aiohttp_overload()
async def fetch_with_aiohttp(session: aiohttp.ClientSession, url: str) -> dict:
    """使用 aiohttp 获取数据，自动处理 429/503 状态码"""
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()


# ============================================================================
# 示例 4: raise_on_aiohttp_overload 装饰异步生成器
# ============================================================================
@raise_on_aiohttp_overload()
async def stream_data_with_aiohttp(
    session: aiohttp.ClientSession, base_url: str
) -> AsyncGenerator[dict, None]:
    """流式获取数据，自动处理HTTP过载错误"""
    for page in range(1, 6):
        url = f"{base_url}?page={page}"
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            for item in data.get("items", []):
                yield item


# ============================================================================
# 示例 5: 自定义过载关键词
# ============================================================================
@raise_on_overload(overload_keywords=("系统繁忙", "请稍后"))
async def custom_keywords_function(task_id: str) -> str:
    """使用自定义关键词检测过载"""
    await asyncio.sleep(0.1)

    if task_id == "busy":
        raise Exception("系统繁忙，请稍后再试")

    return f"任务 {task_id} 完成"


@raise_on_overload(overload_keywords=("系统繁忙", "请稍后"))
async def custom_keywords_generator(task_count: int) -> AsyncGenerator[str, None]:
    """异步生成器使用自定义关键词检测过载"""
    for i in range(task_count):
        await asyncio.sleep(0.1)

        if i == 3:
            raise Exception("系统繁忙，请稍后再试")

        yield f"任务_{i}_完成"


# ============================================================================
# 示例 6: 特定异常类型过滤
# ============================================================================
@raise_on_overload(cared_exception=ConnectionError)
async def specific_exception_function(url: str) -> dict:
    """只关注 ConnectionError 类型的异常"""
    await asyncio.sleep(0.1)

    # ValueError 不会被转换
    if url == "invalid":
        raise ValueError("rate limit exceeded")  # 不会被转换

    # ConnectionError 会被检查并转换
    if url == "overload":
        raise ConnectionError("too many requests")  # 会被转换

    return {"url": url, "status": "ok"}


# ============================================================================
# 主函数：演示所有功能
# ============================================================================
async def main():
    print("=" * 80)
    print("演示 raise_on_overload 和 raise_on_aiohttp_overload 统一装饰器方案")
    print("=" * 80)

    # 示例 1: 普通异步函数成功
    print("\n1️⃣  测试普通异步函数 - 成功情况")
    try:
        result = await fetch_data_with_exception_check("https://api.example.com")
        print(f"✅ 成功: {result}")
    except ServiceOverloadError as e:
        print(f"❌ 服务过载: {e}")

    # 示例 2: 普通异步函数遇到过载
    print("\n2️⃣  测试普通异步函数 - 过载情况")
    try:
        result = await fetch_data_with_exception_check("https://api.overload.com")
        print(f"✅ 成功: {result}")
    except ServiceOverloadError as e:
        print(f"❌ 检测到服务过载: {type(e).__name__}")
        print(f"   原始异常: {e.__cause__}")

    # 示例 3: 异步生成器成功
    print("\n3️⃣  测试异步生成器 - 部分成功")
    try:
        async for item in fetch_pages_with_exception_check("https://api.example.com"):
            print(f"✅ 获取到数据: 第 {item['page']} 页")
    except ServiceOverloadError as e:
        print(f"❌ 在第 3 页检测到服务过载: {type(e).__name__}")
        print(f"   原始异常: {e.__cause__}")

    # 示例 4: 自定义关键词 - 函数
    print("\n4️⃣  测试自定义关键词 - 普通函数")
    try:
        result = await custom_keywords_function("task_1")
        print(f"✅ 成功: {result}")
    except ServiceOverloadError as e:
        print(f"❌ 服务过载: {e}")

    try:
        result = await custom_keywords_function("busy")
        print(f"✅ 成功: {result}")
    except ServiceOverloadError as e:
        print(f"❌ 检测到自定义关键词触发过载: {type(e).__name__}")

    # 示例 5: 自定义关键词 - 生成器
    print("\n5️⃣  测试自定义关键词 - 异步生成器")
    try:
        async for result in custom_keywords_generator(5):
            print(f"✅ 完成: {result}")
    except ServiceOverloadError as e:
        print(f"❌ 生成器在任务 3 检测到过载: {type(e).__name__}")

    # 示例 6: 特定异常类型
    print("\n6️⃣  测试特定异常类型过滤")
    try:
        # ValueError 不会被转换
        result = await specific_exception_function("invalid")
        print(f"✅ 成功: {result}")
    except ValueError as e:
        print(f"⚠️  ValueError 未被转换（预期行为）: {e}")
    except ServiceOverloadError:
        print("❌ 不应该转换 ValueError")

    try:
        # ConnectionError 会被转换
        result = await specific_exception_function("overload")
        print(f"✅ 成功: {result}")
    except ServiceOverloadError as e:
        print(f"❌ ConnectionError 被成功转换: {type(e).__name__}")
        print(f"   原始异常: {e.__cause__}")

    print("\n" + "=" * 80)
    print("✨ 统一装饰器方案的优势:")
    print("   ✅ 一个装饰器同时支持普通函数和生成器")
    print("   ✅ 自动检测函数类型，无需手动选择")
    print("   ✅ 代码更简洁，用户体验更好")
    print("   ✅ 类型安全，IDE 提示友好")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
