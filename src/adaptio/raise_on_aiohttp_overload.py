import functools
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import aiohttp

from .adaptive_async_concurrency_limiter import ServiceOverloadError

OVERLOAD_STATUS_CODES = (503, 429)

T = TypeVar("T")


def raise_on_aiohttp_overload(
    overload_status_codes: tuple[int, ...] = OVERLOAD_STATUS_CODES,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]
]:
    """将 aiohttp 的特定状态码错误转换为 ServiceOverloadError。

    Args:
        overload_status_codes: 要视为过载的 HTTP 状态码元组，默认为 (503, 429)

    Returns:
        装饰器函数，用于包装异步函数

    Raises:
        ServiceOverloadError: 当响应状态码在 overload_status_codes 中时
        aiohttp.ClientResponseError: 其他 HTTP 错误
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except aiohttp.ClientResponseError as e:
                if e.status in overload_status_codes:
                    raise ServiceOverloadError(e) from e
                raise e

        return wrapper

    return decorator
