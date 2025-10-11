import functools
import inspect
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

import aiohttp

from .adaptive_async_concurrency_limiter import ServiceOverloadError

OVERLOAD_STATUS_CODES = (503, 429)

P = ParamSpec("P")
T = TypeVar("T")


def raise_on_aiohttp_overload(
    overload_status_codes: tuple[int, ...] = OVERLOAD_STATUS_CODES,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """将 aiohttp 的特定状态码错误转换为 ServiceOverloadError。

    自动检测被装饰的函数类型：
    - 普通异步函数 (async def func() -> T): 对函数调用进行异常转换
    - 异步生成器 (async def func() -> AsyncGenerator[T, None]): 对生成器迭代进行异常转换

    Args:
        overload_status_codes: 要视为过载的 HTTP 状态码元组，默认为 (503, 429)

    Returns:
        装饰器函数，用于包装异步函数或异步生成器

    Raises:
        ServiceOverloadError: 当响应状态码在 overload_status_codes 中时
        aiohttp.ClientResponseError: 其他 HTTP 错误

    Example:
        ```python
        # 装饰普通异步函数
        @raise_on_aiohttp_overload()
        async def fetch_data(url: str) -> dict:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.json()

        # 装饰异步生成器（自动检测）
        @raise_on_aiohttp_overload()
        async def fetch_pages(base_url: str):
            for page in range(1, 100):
                async with session.get(f"{base_url}?page={page}") as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    for item in data:
                        yield item
        ```
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # 🔍 关键：检测函数类型
        is_async_gen = inspect.isasyncgenfunction(func)

        if is_async_gen:
            # ========== 异步生成器处理逻辑 ==========
            @functools.wraps(func)
            async def generator_wrapper(*args: Any, **kwargs: Any):
                generator = func(*args, **kwargs)
                try:
                    async for item in generator:
                        try:
                            yield item
                        except aiohttp.ClientResponseError as e:
                            if e.status in overload_status_codes:
                                raise ServiceOverloadError(e) from e
                            raise e
                except aiohttp.ClientResponseError as e:
                    if e.status in overload_status_codes:
                        raise ServiceOverloadError(e) from e
                    raise e

            return cast(Callable[P, T], generator_wrapper)

        else:
            # ========== 普通异步函数处理逻辑 ==========
            @functools.wraps(func)
            async def function_wrapper(*args: Any, **kwargs: Any) -> T:
                try:
                    return await func(*args, **kwargs)  # type: ignore[misc]
                except aiohttp.ClientResponseError as e:
                    if e.status in overload_status_codes:
                        raise ServiceOverloadError(e) from e
                    raise e

            return cast(Callable[P, T], function_wrapper)

    return decorator
