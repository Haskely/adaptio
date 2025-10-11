import asyncio
import unittest
from collections.abc import AsyncGenerator

from adaptio.raise_on_overload_by_guessing import (
    OVERLOAD_KEYWORDS,
    ServiceOverloadError,
    raise_on_overload,
)


class TestRaiseOnOverload(unittest.TestCase):
    def __init__(self, *args: str, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.loop: asyncio.AbstractEventLoop

    def setUp(self) -> None:
        # 设置异步测试环境
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        # 清理异步测试环境
        self.loop.close()

    def run_async(self, coro: object) -> object:
        # 辅助函数，运行异步协程
        return self.loop.run_until_complete(coro)  # type: ignore[arg-type]

    def test_success_case(self):
        # 测试正常情况下函数正常返回值
        @raise_on_overload()
        async def success_function():
            return "success"

        result = self.run_async(success_function())
        self.assertEqual(result, "success")

    def test_non_overload_exception(self):
        # 测试非过载异常被正常抛出
        @raise_on_overload()
        async def error_function():
            raise ValueError("一般错误")

        with self.assertRaises(ValueError):
            self.run_async(error_function())

    def test_overload_exception(self):
        # 测试包含过载关键词的异常被转换为ServiceOverloadError
        @raise_on_overload()
        async def overload_function():
            raise ConnectionError("服务暂时 overload，请稍后重试")

        with self.assertRaises(ServiceOverloadError):
            self.run_async(overload_function())

    def test_custom_overload_keywords(self):
        # 测试自定义过载关键词
        custom_keywords = ("自定义错误", "系统繁忙")

        @raise_on_overload(overload_keywords=custom_keywords)
        async def custom_function():
            raise Exception("系统繁忙，请稍后再试")

        with self.assertRaises(ServiceOverloadError):
            self.run_async(custom_function())

    def test_specific_exception_type(self):
        # 测试特定异常类型过滤
        @raise_on_overload(cared_exception=ConnectionError)
        async def specific_exception_function():
            # 这不应该被转换，因为不是ConnectionError
            raise ValueError("rate limit exceeded")

        with self.assertRaises(ValueError):
            self.run_async(specific_exception_function())

    def test_exception_callback(self):
        # 测试使用回调函数来判断异常
        def is_connection_error(e: Exception) -> bool:
            return isinstance(e, ConnectionError)

        @raise_on_overload(cared_exception=is_connection_error)  # type: ignore[arg-type]
        async def callback_function():
            raise ConnectionError("retry later, too many requests")

        with self.assertRaises(ServiceOverloadError):
            self.run_async(callback_function())

    def test_all_predefined_keywords(self):
        @raise_on_overload()
        async def keyword_function(keyword):
            raise Exception(f"Error: {keyword}")

        # 测试所有预定义的关键词
        for keyword in OVERLOAD_KEYWORDS:
            with self.assertRaises(ServiceOverloadError):
                self.run_async(keyword_function(keyword))

    def test_generator_success_case(self):
        """测试异步生成器正常情况下正常产出值"""

        @raise_on_overload()
        async def success_generator() -> AsyncGenerator[str, None]:
            for i in range(5):
                yield f"item_{i}"

        async def run_test() -> list[str]:
            results: list[str] = []
            async for item in success_generator():
                results.append(item)
            return results

        result = self.run_async(run_test())
        self.assertEqual(result, ["item_0", "item_1", "item_2", "item_3", "item_4"])

    def test_generator_non_overload_exception(self):
        """测试异步生成器中非过载异常被正常抛出"""

        @raise_on_overload()
        async def error_generator() -> AsyncGenerator[str, None]:
            yield "item_1"
            raise ValueError("一般错误")

        async def run_test() -> list[str]:
            results: list[str] = []
            async for item in error_generator():
                results.append(item)
            return results

        with self.assertRaises(ValueError):
            self.run_async(run_test())

    def test_generator_overload_exception(self):
        """测试异步生成器中包含过载关键词的异常被转换为ServiceOverloadError"""

        @raise_on_overload()
        async def overload_generator() -> AsyncGenerator[str, None]:
            yield "item_1"
            raise ConnectionError("服务暂时 overload，请稍后重试")

        async def run_test() -> list[str]:
            results: list[str] = []
            async for item in overload_generator():
                results.append(item)
            return results

        with self.assertRaises(ServiceOverloadError):
            self.run_async(run_test())

    def test_generator_custom_overload_keywords(self):
        """测试异步生成器中自定义过载关键词"""
        custom_keywords = ("自定义错误", "系统繁忙")

        @raise_on_overload(overload_keywords=custom_keywords)
        async def custom_generator() -> AsyncGenerator[str, None]:
            for i in range(3):
                if i == 2:
                    raise Exception("系统繁忙，请稍后再试")
                yield f"item_{i}"

        async def run_test() -> list[str]:
            results: list[str] = []
            async for item in custom_generator():
                results.append(item)
            return results

        with self.assertRaises(ServiceOverloadError):
            self.run_async(run_test())

    def test_generator_specific_exception_type(self):
        """测试异步生成器中特定异常类型过滤"""

        @raise_on_overload(cared_exception=ConnectionError)
        async def specific_exception_generator() -> AsyncGenerator[str, None]:
            yield "item_1"
            # 这不应该被转换，因为不是ConnectionError
            raise ValueError("rate limit exceeded")

        async def run_test() -> list[str]:
            results: list[str] = []
            async for item in specific_exception_generator():
                results.append(item)
            return results

        with self.assertRaises(ValueError):
            self.run_async(run_test())

    def test_generator_exception_callback(self):
        """测试异步生成器中使用回调函数来判断异常"""

        def is_connection_error(e: Exception) -> bool:
            return isinstance(e, ConnectionError)

        @raise_on_overload(cared_exception=is_connection_error)  # type: ignore[arg-type]
        async def callback_generator() -> AsyncGenerator[str, None]:
            yield "item_1"
            raise ConnectionError("retry later, too many requests")

        async def run_test() -> list[str]:
            results: list[str] = []
            async for item in callback_generator():
                results.append(item)
            return results

        with self.assertRaises(ServiceOverloadError):
            self.run_async(run_test())


if __name__ == "__main__":
    unittest.main()
