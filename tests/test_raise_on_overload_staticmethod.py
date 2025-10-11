"""测试 raise_on_overload 装饰器对 staticmethod 和 classmethod 的兼容性。"""

import pytest

from adaptio import ServiceOverloadError, raise_on_overload


class TestRaiseOnOverloadStaticMethod:
    """测试 raise_on_overload 对 staticmethod 的支持。"""

    @pytest.mark.asyncio
    async def test_staticmethod_decorator_order_1(self):
        """测试装饰器顺序：@staticmethod 在上，@raise_on_overload 在下。"""

        class API:
            @staticmethod
            @raise_on_overload()
            async def fetch_data(should_fail: bool = False):
                if should_fail:
                    raise RuntimeError("service overload - please retry")
                return {"status": "success"}

        # 测试成功情况
        result = await API.fetch_data(False)
        assert result == {"status": "success"}

        # 测试过载情况
        with pytest.raises(ServiceOverloadError):
            await API.fetch_data(True)

    @pytest.mark.asyncio
    async def test_staticmethod_decorator_order_2(self):
        """测试装饰器顺序：@raise_on_overload 在上，@staticmethod 在下（反向顺序）。"""

        class API:
            @raise_on_overload()
            @staticmethod
            async def fetch_data(should_fail: bool = False):
                if should_fail:
                    raise RuntimeError("service overload - please retry")
                return {"status": "success"}

        # 测试成功情况
        result = await API.fetch_data(False)
        assert result == {"status": "success"}

        # 测试过载情况
        with pytest.raises(ServiceOverloadError):
            await API.fetch_data(True)

    @pytest.mark.asyncio
    async def test_staticmethod_generator_order_1(self):
        """测试 staticmethod async generator：@staticmethod 在上。"""

        class API:
            @staticmethod
            @raise_on_overload()
            async def stream_data(count: int, fail_at: int = -1):
                for i in range(count):
                    if i == fail_at:
                        raise RuntimeError("too many requests")
                    yield i

        # 测试成功情况
        items = []
        async for item in API.stream_data(5):
            items.append(item)
        assert items == [0, 1, 2, 3, 4]

        # 测试过载情况
        items = []
        with pytest.raises(ServiceOverloadError):
            async for item in API.stream_data(5, fail_at=3):
                items.append(item)
        assert items == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_staticmethod_generator_order_2(self):
        """测试 staticmethod async generator：@raise_on_overload 在上。"""

        class API:
            @raise_on_overload()
            @staticmethod
            async def stream_data(count: int, fail_at: int = -1):
                for i in range(count):
                    if i == fail_at:
                        raise RuntimeError("too many requests")
                    yield i

        # 测试成功情况
        items = []
        async for item in API.stream_data(5):
            items.append(item)
        assert items == [0, 1, 2, 3, 4]

        # 测试过载情况
        items = []
        with pytest.raises(ServiceOverloadError):
            async for item in API.stream_data(5, fail_at=3):
                items.append(item)
        assert items == [0, 1, 2]


class TestRaiseOnOverloadClassMethod:
    """测试 raise_on_overload 对 classmethod 的支持。"""

    @pytest.mark.asyncio
    async def test_classmethod_decorator_order_1(self):
        """测试装饰器顺序：@classmethod 在上，@raise_on_overload 在下。"""

        class API:
            name = "TestAPI"

            @classmethod
            @raise_on_overload()
            async def fetch_data(cls, should_fail: bool = False):
                if should_fail:
                    raise RuntimeError("service overload - please retry")
                return {"status": "success", "api": cls.name}

        # 测试成功情况
        result = await API.fetch_data(False)
        assert result == {"status": "success", "api": "TestAPI"}

        # 测试过载情况
        with pytest.raises(ServiceOverloadError):
            await API.fetch_data(True)

    @pytest.mark.asyncio
    async def test_classmethod_decorator_order_2(self):
        """测试装饰器顺序：@raise_on_overload 在上，@classmethod 在下。"""

        class API:
            name = "TestAPI"

            @raise_on_overload()
            @classmethod
            async def fetch_data(cls, should_fail: bool = False):
                if should_fail:
                    raise RuntimeError("service overload - please retry")
                return {"status": "success", "api": cls.name}

        # 测试成功情况
        result = await API.fetch_data(False)
        assert result == {"status": "success", "api": "TestAPI"}

        # 测试过载情况
        with pytest.raises(ServiceOverloadError):
            await API.fetch_data(True)

    @pytest.mark.asyncio
    async def test_classmethod_generator_order_1(self):
        """测试 classmethod async generator：@classmethod 在上。"""

        class API:
            name = "TestAPI"

            @classmethod
            @raise_on_overload()
            async def stream_data(cls, count: int, fail_at: int = -1):
                for i in range(count):
                    if i == fail_at:
                        raise RuntimeError("too many requests")
                    yield {"index": i, "api": cls.name}

        # 测试成功情况
        items = []
        async for item in API.stream_data(3):
            items.append(item)
        assert len(items) == 3
        assert all(item["api"] == "TestAPI" for item in items)

        # 测试过载情况
        items = []
        with pytest.raises(ServiceOverloadError):
            async for item in API.stream_data(5, fail_at=2):
                items.append(item)
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_classmethod_generator_order_2(self):
        """测试 classmethod async generator：@raise_on_overload 在上。"""

        class API:
            name = "TestAPI"

            @raise_on_overload()
            @classmethod
            async def stream_data(cls, count: int, fail_at: int = -1):
                for i in range(count):
                    if i == fail_at:
                        raise RuntimeError("too many requests")
                    yield {"index": i, "api": cls.name}

        # 测试成功情况
        items = []
        async for item in API.stream_data(3):
            items.append(item)
        assert len(items) == 3
        assert all(item["api"] == "TestAPI" for item in items)

        # 测试过载情况
        items = []
        with pytest.raises(ServiceOverloadError):
            async for item in API.stream_data(5, fail_at=2):
                items.append(item)
        assert len(items) == 2
