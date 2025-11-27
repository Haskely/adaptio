import asyncio
import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from adaptio.adaptive_async_concurrency_limiter import (
    AdaptiveAsyncConcurrencyLimiter,
    ServiceOverloadError,
)

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


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
    ignore_loop_bound_exception: bool = True,
):
    """装饰器：为异步函数或异步生成器添加自适应重试机制。

    自动检测被装饰的函数类型：
    - 普通异步函数 (async def func() -> T): 对函数调用进行并发控制
    - 异步生成器 (async def func() -> AsyncGenerator[T, None]): 对生成器迭代进行并发控制

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
        ignore_loop_bound_exception: 是否忽略事件循环绑定异常
            如果在另一个 asyncio 循环中使用信号量，标准信号量会引发 RuntimeError。
            设置为 True（默认）时，会为每个 event loop 创建独立的信号量实例（LoopLocalAdjustableSemaphore），
            这样每个 loop 都有自己独立的并发限制，避免跨 loop 使用异常。
            设置为 False 时，使用标准信号量，跨 loop 使用时会抛出 RuntimeError。
            通常情况下很难在实际应用中触发这个错误，除非刻意写出在同步函数中使用多线程调用异步函数的代码。
            https://github.com/python/cpython/blob/v3.13.3/Lib/asyncio/mixins.py#L20

    Returns:
        装饰后的函数，具有自适应重试能力

    Example:
        ```python
        # 装饰普通异步函数
        @with_adaptive_retry()
        async def fetch_data(url: str) -> dict:
            async with session.get(url) as resp:
                if resp.status == 429:
                    raise ServiceOverloadError("Rate limited")
                return await resp.json()

        # 装饰异步生成器（自动检测）
        @with_adaptive_retry()
        async def fetch_pages(base_url: str):
            for page in range(1, 100):
                data = await fetch_page(f"{base_url}?page={page}")
                for item in data:
                    yield item
        ```
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

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        if not _scheduler.log_prefix:
            _scheduler.log_prefix = getattr(func, "__name__", "unnamed_function")

        retry_logger = logging.getLogger(f"retry_{id(func)}")

        # 🔍 关键：检测函数类型
        is_async_gen = inspect.isasyncgenfunction(func)

        if is_async_gen:
            # ========== 异步生成器处理逻辑 ==========
            @wraps(func)
            async def generator_wrapper(*args, **kwargs):
                retries = 0

                while True:
                    try:
                        async with _scheduler.workers_lock:
                            _scheduler.current_running_count += 1

                            try:
                                # 创建并迭代生成器
                                generator = func(*args, **kwargs)
                                item_count = 0

                                async for item in generator:
                                    yield item
                                    item_count += 1

                                # 成功完成
                                _scheduler.current_succeed_count += 1
                                retry_logger.debug(
                                    f"{_scheduler.log_prefix} -- "
                                    f"生成器成功完成，产出 {item_count} 个项目"
                                )
                                return  # 成功退出

                            except _scheduler.overload_exception as e:
                                _scheduler.current_overload_count += 1
                                retries += 1

                                if retries > max_retries:
                                    retry_logger.error(
                                        f"{_scheduler.log_prefix} -- "
                                        f"重试次数已达上限({retries}次)，生成器仍处于过载状态"
                                    )
                                    raise

                                retry_logger.warning(
                                    f"{_scheduler.log_prefix} -- "
                                    f"生成器触发过载 (尝试 {retries}/{max_retries}): {e}"
                                )

                                # 等待后重试整个生成器
                                await asyncio.sleep(retry_interval_seconds)
                                continue  # 重新开始

                            except Exception:
                                _scheduler.current_failed_count += 1
                                raise

                            finally:
                                _scheduler.current_finished_count += 1
                                _scheduler.current_running_count -= 1

                                # 调整并发度
                                if _scheduler.workers_lock.get_value() < 0:
                                    _scheduler.reset_counters()

                                if (
                                    _scheduler.current_finished_count
                                    > _scheduler.workers_lock.initial_value
                                ):
                                    await _scheduler.adjust_concurrency()
                                    _scheduler.reset_counters()

                        # 如果没有异常，break 退出重试循环
                        break

                    except _scheduler.overload_exception:
                        if retries > max_retries:
                            raise
                        continue

            return generator_wrapper

        else:
            # ========== 普通异步函数处理逻辑（保持原有实现）==========
            @wraps(func)
            async def function_wrapper(*args: Any, **kwargs: Any) -> Any:
                retries = 0

                while True:
                    try:
                        coro = func(*args, **kwargs)
                        task = _scheduler.submit(coro)  # type: ignore[arg-type]
                        return await task  # type: ignore
                    except _scheduler.overload_exception:
                        retries += 1
                        if retries > max_retries:
                            retry_logger.error(
                                f"{_scheduler.log_prefix} -- "
                                f"重试次数已达上限({retries}次)，服务仍处于过载状态"
                            )
                            raise
                        await asyncio.sleep(retry_interval_seconds)
                        continue

            return function_wrapper

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

    @with_adaptive_retry(
        initial_concurrency=4, log_level="DEBUG", ignore_loop_bound_exception=False
    )
    async def sample_task_with_retry(task_id: int) -> str:
        return await sample_task(task_id)  # type: ignore[arg-type]

    async def get_result():
        tasks = [sample_task_with_retry(i) for i in range(200)]
        for res in asyncio.as_completed(tasks):
            try:
                logging.info(f"SUCCESS: {await res}")
            except Exception as e:
                logging.error(f"error: {e}")
                pass

    asyncio.run(get_result())
