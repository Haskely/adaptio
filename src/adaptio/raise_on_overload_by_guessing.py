import functools
import inspect
from collections.abc import Callable, Iterable
from typing import Any, ParamSpec, TypeVar, cast

from .adaptive_async_concurrency_limiter import ServiceOverloadError

P = ParamSpec("P")
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
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """将包含过载关键词的 Exception 转换为 ServiceOverloadError。

    自动检测被装饰的函数类型：
    - 普通异步函数 (async def func() -> T): 对函数调用进行异常转换
    - 异步生成器 (async def func() -> AsyncGenerator[T, None]): 对生成器迭代进行异常转换

    Args:
        overload_keywords: 要视为过载的关键词元组，默认为 OVERLOAD_KEYWORDS
        cared_exception: 需要捕获的异常类型或者一个输入为异常对象的函数

    Returns:
        装饰器函数，用于包装异步函数或异步生成器

    Raises:
        ServiceOverloadError: 当响应包含过载关键词时

    Example:
        ```python
        # 装饰普通异步函数
        @raise_on_overload()
        async def fetch_data(url: str) -> dict:
            async with session.get(url) as resp:
                return await resp.json()

        # 装饰异步生成器（自动检测）
        @raise_on_overload()
        async def fetch_pages(base_url: str):
            for page in range(1, 100):
                data = await fetch_page(f"{base_url}?page={page}")
                for item in data:
                    yield item
        ```
    """
    if not isinstance(cared_exception, Iterable):
        cared_exception = (cared_exception,)

    def is_cared_exception(e: Exception) -> bool:
        for cared_e in cared_exception:
            if isinstance(cared_e, type):
                if isinstance(e, cared_e):
                    return True
            elif callable(cared_e):  # type: ignore[arg-type]
                # cared_e 是一个可调用对象，类型检查器知道它是 Callable[[Exception], bool]
                result = cared_e(e)  # type: ignore[misc]
                if result is True:
                    return True
        return False

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
                        except Exception as e:
                            if is_cared_exception(e):
                                exception_str = str(e)
                                if any(
                                    keyword in exception_str
                                    for keyword in overload_keywords
                                ):
                                    raise ServiceOverloadError(e) from e
                            raise e
                except Exception as e:
                    if is_cared_exception(e):
                        exception_str = str(e)
                        if any(
                            keyword in exception_str for keyword in overload_keywords
                        ):
                            raise ServiceOverloadError(e) from e
                    raise e

            return cast(Callable[P, T], generator_wrapper)

        else:
            # ========== 普通异步函数处理逻辑 ==========
            @functools.wraps(func)
            async def function_wrapper(*args: Any, **kwargs: Any) -> T:
                try:
                    return await func(*args, **kwargs)  # type: ignore[misc]
                except Exception as e:
                    if is_cared_exception(e):
                        exception_str = str(e)
                        if any(
                            keyword in exception_str for keyword in overload_keywords
                        ):
                            raise ServiceOverloadError(e) from e
                    raise e

            return cast(Callable[P, T], function_wrapper)

    return decorator
