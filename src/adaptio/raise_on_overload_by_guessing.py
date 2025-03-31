import functools
from collections.abc import Callable, Coroutine, Iterable
from typing import Any, TypeVar

from .adaptive_async_concurrency_limiter import ServiceOverloadError

T = TypeVar("T")

OVERLOAD_KEYWORDS = (
    "overload",
    "temporarily unavailable",
    "service unavailable",
    "too many requests",
    "rate limit",
    "rate limited",
    "try again",
    "retry",
    "busy",
    "too many",
)


def raise_on_overload(
    overload_keywords: tuple[str, ...] = OVERLOAD_KEYWORDS,
    cared_exception: type[Exception]
    | Callable[[Exception], bool]
    | Iterable[Callable[[Exception], bool] | type[Exception]] = Exception,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]
]:
    """将包含过载关键词的 Exception 转换为 ServiceOverloadError。

    Args:
        overload_keywords: 要视为过载的关键词元组，默认为 OVERLOAD_KEYWORDS
        cared_exception: 需要捕获的异常类型或者一个输入为异常对象的函数

    Returns:
        装饰器函数，用于包装异步函数

    Raises:
        ServiceOverloadError: 当响应包含过载关键词时
    """
    if not isinstance(cared_exception, Iterable):
        cared_exception = (cared_exception,)

    def is_cared_exception(e: Exception) -> bool:
        for cared_e in cared_exception:
            if isinstance(cared_e, type):
                if isinstance(e, cared_e):
                    return True
            elif callable(cared_e) and cared_e(e) is True:
                return True
        return False

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if is_cared_exception(e):
                    exception_str = str(e)
                    if any(keyword in exception_str for keyword in overload_keywords):
                        raise ServiceOverloadError(e) from e
                raise e

        return wrapper

    return decorator
