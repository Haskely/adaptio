import asyncio
import unittest

from adaptio.raise_on_overload_by_guessing import (
    OVERLOAD_KEYWORDS,
    ServiceOverloadError,
    raise_on_overload,
)


class TestRaiseOnOverload(unittest.TestCase):
    def setUp(self):
        # 设置异步测试环境
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        # 清理异步测试环境
        self.loop.close()

    def run_async(self, coro):
        # 辅助函数，运行异步协程
        return self.loop.run_until_complete(coro)

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
        def is_connection_error(e):
            return isinstance(e, ConnectionError)

        @raise_on_overload(cared_exception=is_connection_error)
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


if __name__ == "__main__":
    unittest.main()
