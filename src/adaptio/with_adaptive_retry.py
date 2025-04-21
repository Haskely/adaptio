import asyncio
import logging
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, TypeVar

from adaptio.adaptive_async_concurrency_limiter import (
    AdaptiveAsyncConcurrencyLimiter,
    ServiceOverloadError,
)

R = TypeVar("R")


def with_adaptive_retry(
    scheduler: AdaptiveAsyncConcurrencyLimiter | None = None,
    max_retries: int = 1024,
    retry_interval_seconds: float = 1,
    max_concurrency: int = 256,
    min_concurrency: int = 1,
    initial_concurrency: int = 1,
    adjust_overload_rate: float = 0.1,
    overload_exception: type[BaseException] = ServiceOverloadError,
    log_level: str = "INFO",
    log_prefix: str = "",
    ignore_loop_bound_exception: bool = False,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, R]]], Callable[..., Coroutine[Any, Any, R]]
]:
    """装饰器：为异步函数添加自适应重试机制。

    当函数触发过载异常时，会自动重试并通过 AdaptiveConcurrencyLimiter 动态调整并发数。

    Args:
        scheduler: AdaptiveConcurrencyLimiter 实例。如果为 None，则为每个装饰的函数创建独立的限制器
        max_retries: 最大重试次数
        retry_interval_seconds: 重试间隔时间（秒）
        max_concurrency: 当 scheduler 为 None 时使用的最大并发数
        min_concurrency: 当 scheduler 为 None 时使用的最小并发数
        initial_concurrency: 当 scheduler 为 None 时使用的初始并发数
        adjust_overload_rate: 当 scheduler 为 None 时使用的过载调整率
            意思是在最近一轮并发调用中，若触发过载错误的调用数量超过这个比例，才会进行降低并发数操作
        overload_exception: 当 scheduler 为 None 时检测的过载异常类型
        log_level: 当 scheduler 为 None 时使用的日志级别
        log_prefix: 当 scheduler 为 None 时使用的日志前缀
        ignore_loop_bound_exception: 是否忽略循环边界异常
            如果你获取了一个在另一个asyncio循环中初始化的信号量，实际上它没有任何限制并发的能力！
            默认情况下，这个库在这种情况下会引发RuntimeError异常。
            但是，如果你将此选项设置为True，它将忽略异常，并且除了打印一条 warning 外没有其他动作。
            通常情况下很难在实际应用中出发这个错误，除非刻意写出在同步函数中使用多线程调用异步函数的代码。
            https://github.com/python/cpython/blob/v3.13.3/Lib/asyncio/mixins.py#L20

    Returns:
        装饰后的异步函数，具有自适应重试能力
    """
    # 如果没有传入 scheduler，则创建一个新的限制器实例
    _scheduler = scheduler or AdaptiveAsyncConcurrencyLimiter(
        max_concurrency=max_concurrency,
        min_concurrency=min_concurrency,
        initial_concurrency=initial_concurrency,
        adjust_overload_rate=adjust_overload_rate,
        overload_exception=overload_exception,
        log_level=log_level,
        log_prefix=log_prefix,
        ignore_loop_bound_exception=ignore_loop_bound_exception,
    )

    def decorator(
        func: Callable[..., Coroutine[Any, Any, R]],
    ) -> Callable[..., Coroutine[Any, Any, R]]:
        if not _scheduler.log_prefix:
            _scheduler.log_prefix = getattr(func, "__name__", "unnamed_function")

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> R:
            retries = 0
            # 为装饰器创建独立的 logger
            retry_logger = logging.getLogger(f"retry_{id(func)}")
            while True:
                try:
                    task = _scheduler.submit(func(*args, **kwargs))
                    return await task  # type: ignore
                except _scheduler.overload_exception:
                    retries += 1
                    if retries > max_retries:
                        retry_logger.error(
                            f"{_scheduler.log_prefix} -- 重试次数已达上限({retries}次)，服务仍处于过载状态"
                        )
                        raise
                    await asyncio.sleep(retry_interval_seconds)
                    continue

        return wrapper

    return decorator


if __name__ == "__main__":
    import random

    # 设计一个达到 32 并发就会触发 ServiceOverloadError 的测试任务
    sample_task_overload_threshold = 32
    sample_task_running_count = 0

    async def sample_task(task_id):
        """A sample task that simulates workload and triggers overload at a certain concurrency."""
        global sample_task_running_count
        sample_task_running_count += 1
        # 模拟随机任务耗时
        await asyncio.sleep(random.uniform(1, 3))
        # 模拟过载错误

        if sample_task_running_count > sample_task_overload_threshold:
            sample_task_running_count -= 1
            logging.error(
                f"===sample_task {sample_task_running_count} tasks > {sample_task_overload_threshold}==="
            )
            raise ServiceOverloadError(
                f"Service overloaded with {sample_task_running_count} tasks > {sample_task_overload_threshold}"
            )
        else:
            sample_task_running_count -= 1
        return f"Task {task_id} done"

    @with_adaptive_retry(initial_concurrency=4, log_level="INFO")
    async def sample_task_with_retry(task_id):
        return await sample_task(task_id)

    async def get_result():
        tasks = [sample_task_with_retry(i) for i in range(1000)]
        for res in asyncio.as_completed(tasks):
            try:
                logging.info(f"SUCCESS: {await res}")
            except Exception as e:
                logging.error(f"error: {e}")
                pass

    asyncio.run(get_result())
