"""装饰器工具函数模块。

提供用于处理 staticmethod 和 classmethod 装饰器的通用工具函数。
"""

import inspect
from collections.abc import Callable
from typing import Any, TypeVar, cast

T = TypeVar("T")


def unwrap_static_class_method(
    func: Callable[..., T],
) -> tuple[Callable[..., T], bool, bool]:
    """提取被 staticmethod 或 classmethod 包装的真实函数。

    Args:
        func: 可能被 staticmethod/classmethod 包装的函数

    Returns:
        元组 (actual_func, is_static, is_class):
        - actual_func: 真实的函数对象
        - is_static: 是否为 staticmethod
        - is_class: 是否为 classmethod
    """
    is_static = isinstance(func, staticmethod)
    is_class = isinstance(func, classmethod)

    # 提取真实函数（如果被 staticmethod/classmethod 包装）
    actual_func = (
        func.__func__  # type: ignore[union-attr,return-value]
        if is_static or is_class
        else func
    )

    return actual_func, is_static, is_class


def rewrap_static_class_method(
    wrapper_func: Callable[..., T],
    is_static: bool,
    is_class: bool,
) -> Callable[..., T]:
    """根据原始装饰器类型重新包装函数。

    Args:
        wrapper_func: 包装后的函数
        is_static: 是否需要包装为 staticmethod
        is_class: 是否需要包装为 classmethod

    Returns:
        重新包装后的函数
    """
    if is_static:
        return cast(Callable[..., T], staticmethod(wrapper_func))  # type: ignore[arg-type]
    elif is_class:
        return cast(Callable[..., T], classmethod(wrapper_func))  # type: ignore[arg-type]
    else:
        return wrapper_func


def is_async_generator_function(func: Any) -> bool:
    """检测函数是否为异步生成器，兼容 staticmethod/classmethod。

    Args:
        func: 要检测的函数对象

    Returns:
        是否为异步生成器函数
    """
    actual_func, _, _ = unwrap_static_class_method(func)
    return inspect.isasyncgenfunction(actual_func)  # type: ignore[arg-type]
