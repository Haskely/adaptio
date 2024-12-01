import asyncio
import unittest
from typing import Any
from unittest.mock import AsyncMock

import aiohttp

from adaptio import ServiceOverloadError, raise_on_aiohttp_overload


class TestAiohttpOverloadDecorator(unittest.TestCase):
    """测试 raise_on_aiohttp_overload 装饰器的行为。"""

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_successful_request(self) -> None:
        """测试正常请求场景。"""

        @raise_on_aiohttp_overload()
        async def sample_request() -> str:
            return "success"

        result = self.loop.run_until_complete(sample_request())
        self.assertEqual(result, "success")

    def test_overload_error_503(self) -> None:
        """测试 503 状态码时是否正确抛出 ServiceOverloadError。"""

        @raise_on_aiohttp_overload()
        async def failing_request() -> Any:
            raise aiohttp.ClientResponseError(
                request_info=AsyncMock(), history=(), status=503
            )

        with self.assertRaises(ServiceOverloadError):
            self.loop.run_until_complete(failing_request())

    def test_overload_error_429(self) -> None:
        """测试 429 状态码时是否正确抛出 ServiceOverloadError。"""

        @raise_on_aiohttp_overload()
        async def failing_request() -> Any:
            raise aiohttp.ClientResponseError(
                request_info=AsyncMock(), history=(), status=429
            )

        with self.assertRaises(ServiceOverloadError):
            self.loop.run_until_complete(failing_request())

    def test_other_error(self) -> None:
        """测试其他状态码时是否正确抛出 aiohttp.ClientResponseError。"""

        @raise_on_aiohttp_overload()
        async def failing_request() -> Any:
            raise aiohttp.ClientResponseError(
                request_info=AsyncMock(), history=(), status=404
            )

        with self.assertRaises(aiohttp.ClientResponseError):
            self.loop.run_until_complete(failing_request())

    def test_custom_overload_status_codes(self) -> None:
        """测试自定义状态码的情况。"""

        @raise_on_aiohttp_overload(overload_status_codes=(418,))
        async def failing_request() -> Any:
            raise aiohttp.ClientResponseError(
                request_info=AsyncMock(), history=(), status=418
            )

        with self.assertRaises(ServiceOverloadError):
            self.loop.run_until_complete(failing_request())

    def test_multiple_custom_status_codes(self) -> None:
        """测试多个自定义状态码的情况。"""

        @raise_on_aiohttp_overload(overload_status_codes=(418, 420))
        async def failing_request() -> Any:
            raise aiohttp.ClientResponseError(
                request_info=AsyncMock(), history=(), status=420
            )

        with self.assertRaises(ServiceOverloadError):
            self.loop.run_until_complete(failing_request())

    def test_non_aiohttp_error(self) -> None:
        """测试非 aiohttp 异常的情况。"""

        @raise_on_aiohttp_overload()
        async def failing_request() -> Any:
            raise ValueError("其他错误")

        with self.assertRaises(ValueError):
            self.loop.run_until_complete(failing_request())


if __name__ == "__main__":
    unittest.main()
