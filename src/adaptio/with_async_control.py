import asyncio
from collections.abc import Awaitable, Coroutine
from functools import wraps
from typing import Any, Callable, TypeVar

from .log_utils import setup_colored_logger

T = TypeVar("T")

# 设置logger
logger = setup_colored_logger(__name__)


class FakeLock:
    """空锁实现，用于不需要并发控制时"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def with_async_control(
    exception_type: type[Exception] | tuple[type[Exception], ...] = Exception,
    max_concurrency: int = 0,
    max_qps: float = 0,
    retry_n: int = 3,
    retry_delay: float = 1.0,
    raise_after_retry: bool = True,
) -> Callable[
    [Callable[..., Awaitable[T]]], Callable[..., Coroutine[Any, Any, T | Exception]]
]:
    """
    异步函数的装饰器，提供并发限制、QPS控制和重试功能

    参数:
        exception_type: 需要捕获的异常类型
        max_concurrency: 最大并发数
        max_qps: 每秒最大请求数 (0表示不限制)
        retry_n: 重试次数
        retry_delay: 重试间隔时间(秒)
        raise_after_retry: 重试失败后是否抛出异常

    返回:
        装饰器函数
    """

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Coroutine[Any, Any, T | Exception]]:
        # 为每个装饰器实例创建独立的锁
        concurrency_sem = (
            asyncio.Semaphore(max_concurrency) if max_concurrency > 0 else FakeLock()
        )
        qps_lock = asyncio.Lock()

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T | Exception:
            async with concurrency_sem:
                for attempt in range(retry_n + 1):
                    try:
                        if max_qps > 1e-5:  # 避免浮点数精度问题
                            async with qps_lock:
                                await asyncio.sleep(1 / max_qps)
                        return await func(*args, **kwargs)
                    except exception_type as e:
                        logger.error(
                            f"（{attempt+1}/{retry_n}） 尝试 {func.__name__} 失败: \n Class: {e.__class__.__name__}\n Message: {e}"
                        )
                        if attempt >= retry_n:
                            logger.error(
                                f"（{attempt+1}/{retry_n}） 尝试 {func.__name__} 达到最大次数！"
                            )
                            if raise_after_retry:
                                raise
                            else:
                                return e
                        await asyncio.sleep(retry_delay)
                raise Exception("所有重试都失败了")

        return wrapper

    return decorator


if __name__ == "__main__":
    import time

    @with_async_control(
        exception_type=ValueError,
        max_concurrency=5,
        max_qps=10,
        retry_n=3,
        retry_delay=0.5,
        raise_after_retry=False,
    )
    async def test_api(i: int) -> str:
        # 模拟一个可能失败的API调用
        if i % 3 == 2:  # 让每三个请求中的一个失败
            raise ValueError(f"模拟 ValueError错误 - 请求 {i}")
        if i % 3 == 1:
            raise RuntimeError(f"模拟 RuntimeError 错误 - 请求 {i}")
        await asyncio.sleep(1.0)  # 模拟API延迟
        return f"请求 {i} 成功"

    async def main():
        print("开始测试...")
        start_time = time.time()

        # 创建5个并发任务
        tasks = [test_api(i) for i in range(10)]

        # 打印结果
        for i, future in enumerate(asyncio.as_completed(tasks)):
            try:
                result = await future
                logger.success(f"任务 {i} 成功: {result}")
            except Exception as e:
                logger.warning(
                    f"任务 {i} 失败: \n Class: {e.__class__.__name__}\n Message: {e}"
                )

        end_time = time.time()
        print(f"\n总耗时: {end_time - start_time:.2f}秒")

    # 运行测试
    asyncio.run(main())