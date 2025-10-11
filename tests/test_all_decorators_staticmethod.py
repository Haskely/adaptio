"""测试所有装饰器对 staticmethod 和 classmethod 的兼容性。

验证以下装饰器：
- raise_on_overload
- raise_on_aiohttp_overload
- with_async_control
"""

from unittest.mock import AsyncMock

import pytest

from adaptio import (
    ServiceOverloadError,
    raise_on_aiohttp_overload,
    raise_on_overload,
    with_async_control,
)


class TestAllDecoratorsStaticMethod:
    """测试所有装饰器对 staticmethod 的支持。"""

    @pytest.mark.asyncio
    async def test_raise_on_overload_staticmethod(self):
        """测试 raise_on_overload 装饰 staticmethod。"""

        class API:
            @staticmethod
            @raise_on_overload()
            async def fetch():
                raise RuntimeError("service overload")

        with pytest.raises(ServiceOverloadError):
            await API.fetch()

    @pytest.mark.asyncio
    async def test_raise_on_aiohttp_overload_staticmethod(self):
        """测试 raise_on_aiohttp_overload 装饰 staticmethod。"""
        import aiohttp

        class API:
            @staticmethod
            @raise_on_aiohttp_overload()
            async def fetch():
                raise aiohttp.ClientResponseError(
                    request_info=AsyncMock(),
                    history=(),
                    status=429,
                    message="Too Many Requests",
                )

        with pytest.raises(ServiceOverloadError):
            await API.fetch()

    @pytest.mark.asyncio
    async def test_with_async_control_staticmethod(self):
        """测试 with_async_control 装饰 staticmethod。"""

        class API:
            @staticmethod
            @with_async_control(max_concurrency=2, retry_n=1)
            async def fetch():
                return "success"

        result = await API.fetch()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_raise_on_overload_staticmethod_generator(self):
        """测试 raise_on_overload 装饰 staticmethod async generator。"""

        class API:
            @staticmethod
            @raise_on_overload()
            async def stream():
                for i in range(3):
                    yield i
                raise RuntimeError("service overload")

        items = []
        with pytest.raises(ServiceOverloadError):
            async for item in API.stream():
                items.append(item)
        assert items == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_with_async_control_staticmethod_generator(self):
        """测试 with_async_control 装饰 staticmethod async generator。"""

        class API:
            @staticmethod
            @with_async_control(max_concurrency=2)
            async def stream():
                for i in range(5):
                    yield i

        items = []
        async for item in API.stream():
            items.append(item)
        assert items == [0, 1, 2, 3, 4]


class TestAllDecoratorsClassMethod:
    """测试所有装饰器对 classmethod 的支持。"""

    @pytest.mark.asyncio
    async def test_raise_on_overload_classmethod(self):
        """测试 raise_on_overload 装饰 classmethod。"""

        class API:
            name = "TestAPI"

            @classmethod
            @raise_on_overload()
            async def fetch(cls):
                raise RuntimeError("service overload")

        with pytest.raises(ServiceOverloadError):
            await API.fetch()

    @pytest.mark.asyncio
    async def test_raise_on_aiohttp_overload_classmethod(self):
        """测试 raise_on_aiohttp_overload 装饰 classmethod。"""
        import aiohttp

        class API:
            @classmethod
            @raise_on_aiohttp_overload()
            async def fetch(cls):
                raise aiohttp.ClientResponseError(
                    request_info=AsyncMock(),
                    history=(),
                    status=503,
                    message="Service Unavailable",
                )

        with pytest.raises(ServiceOverloadError):
            await API.fetch()

    @pytest.mark.asyncio
    async def test_with_async_control_classmethod(self):
        """测试 with_async_control 装饰 classmethod。"""

        class API:
            @classmethod
            @with_async_control(max_concurrency=2, retry_n=1)
            async def fetch(cls):
                return "success"

        result = await API.fetch()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_raise_on_overload_classmethod_generator(self):
        """测试 raise_on_overload 装饰 classmethod async generator。"""

        class API:
            @classmethod
            @raise_on_overload()
            async def stream(cls):
                for i in range(3):
                    yield i
                raise RuntimeError("service overload")

        items = []
        with pytest.raises(ServiceOverloadError):
            async for item in API.stream():
                items.append(item)
        assert items == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_with_async_control_classmethod_generator(self):
        """测试 with_async_control 装饰 classmethod async generator。"""

        class API:
            @classmethod
            @with_async_control(max_concurrency=2)
            async def stream(cls):
                for i in range(5):
                    yield i

        items = []
        async for item in API.stream():
            items.append(item)
        assert items == [0, 1, 2, 3, 4]


class TestReverseDecoratorOrder:
    """测试反向装饰器顺序的兼容性。"""

    @pytest.mark.asyncio
    async def test_raise_on_overload_reverse_order(self):
        """测试 @raise_on_overload 在 @staticmethod 上方。"""

        class API:
            @raise_on_overload()
            @staticmethod
            async def fetch():
                raise RuntimeError("service overload")

        with pytest.raises(ServiceOverloadError):
            await API.fetch()

    @pytest.mark.asyncio
    async def test_with_async_control_reverse_order(self):
        """测试 @with_async_control 在 @staticmethod 上方。"""

        class API:
            @with_async_control(max_concurrency=2)
            @staticmethod
            async def fetch():
                return "success"

        result = await API.fetch()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_raise_on_overload_reverse_order_generator(self):
        """测试 @raise_on_overload 在 @staticmethod 上方（generator）。"""

        class API:
            @raise_on_overload()
            @staticmethod
            async def stream():
                for i in range(3):
                    yield i
                raise RuntimeError("service overload")

        items = []
        with pytest.raises(ServiceOverloadError):
            async for item in API.stream():
                items.append(item)
        assert items == [0, 1, 2]
