import functools
from collections.abc import Callable, Iterable
from typing import Any, ParamSpec, TypeVar, cast

from .adaptive_async_concurrency_limiter import ServiceOverloadError
from .decorator_utils import (
    is_async_generator_function,
    rewrap_static_class_method,
    unwrap_static_class_method,
)

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

    支持与 @staticmethod 和 @classmethod 装饰器组合使用，且兼容两种装饰器顺序：
    - 推荐顺序：@staticmethod/@classmethod 在上，@raise_on_overload 在下
    - 也支持：@raise_on_overload 在上，@staticmethod/@classmethod 在下

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

        # 与 @staticmethod 组合使用（两种顺序都支持）
        class API:
            # 推荐方式
            @staticmethod
            @raise_on_overload()
            async def fetch_static():
                ...

            # 也支持
            @raise_on_overload()
            @staticmethod
            async def fetch_alt():
                ...
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
        # 🔍 兼容性处理：检测是否被 staticmethod/classmethod 包装
        actual_func, is_static, is_class = unwrap_static_class_method(func)

        # 🔍 关键：检测函数类型
        is_async_gen = is_async_generator_function(func)

        if is_async_gen:
            # ========== 异步生成器处理逻辑 ==========
            @functools.wraps(actual_func)  # type: ignore[arg-type]
            async def generator_wrapper(*args: Any, **kwargs: Any):
                generator = actual_func(*args, **kwargs)  # type: ignore[misc,operator]
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

            # 如果原来是 staticmethod/classmethod，需要重新包装
            return cast(
                Callable[P, T],
                rewrap_static_class_method(generator_wrapper, is_static, is_class),
            )  # type: ignore[arg-type]

        else:
            # ========== 普通异步函数处理逻辑 ==========
            @functools.wraps(actual_func)  # type: ignore[arg-type]
            async def function_wrapper(*args: Any, **kwargs: Any) -> T:
                try:
                    return await actual_func(*args, **kwargs)  # type: ignore[misc]
                except Exception as e:
                    if is_cared_exception(e):
                        exception_str = str(e)
                        if any(
                            keyword in exception_str for keyword in overload_keywords
                        ):
                            raise ServiceOverloadError(e) from e
                    raise e

            # 如果原来是 staticmethod/classmethod，需要重新包装
            return cast(
                Callable[P, T],
                rewrap_static_class_method(function_wrapper, is_static, is_class),
            )  # type: ignore[arg-type]

    return decorator
