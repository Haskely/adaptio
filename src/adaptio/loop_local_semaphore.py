import asyncio
import weakref


class LoopLocalSemaphore:
    """
    LoopLocalSemaphore: 为每个 event loop 自动分配一个 asyncio.Semaphore。

    - 同一个 LoopLocalSemaphore 实例，可以在多个线程 / 多个 event loop 下使用。
    - 每个 loop 拿到的都是"自己的那个 asyncio.Semaphore"，互相之间独立，不共享状态。
    - 主要用途：避免 asyncio.Semaphore 在多线程、多 loop 场景下的
      "RuntimeError: <Semaphore ...> is bound to a different event loop"。

    注意：
    ----
    这个类 **不是** 跨 loop / 跨线程互斥。
    它提供的是"按 loop 局部并发限制"，更多是为了代码架构上的方便，避免错误。
    如果你需要跨线程全局并发控制，请使用其他同步原语。
    """

    def __init__(self, value: int = 1) -> None:
        """
        初始化 LoopLocalSemaphore。

        参数:
            value: Semaphore 的初始值（即允许的最大并发数），默认为 1
        """
        if value < 0:
            raise ValueError("Semaphore initial value must be >= 0")
        self._value = value
        # key: loop (弱引用), value: asyncio.Semaphore (强引用)
        self._semaphores: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, asyncio.Semaphore
        ] = weakref.WeakKeyDictionary()

    def _get_current_loop(self) -> asyncio.AbstractEventLoop:
        """
        获取当前正在运行的 event loop。
        必须在 coroutine 中调用（即有 running loop）。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 在未运行的线程 / 非 coroutine 环境下调用会报错。
            raise RuntimeError(
                "LoopLocalSemaphore must be used inside an asyncio event loop "
                "(i.e., inside an `async def` function)."
            ) from None
        return loop

    def _get_semaphore_for_current_loop(self) -> asyncio.Semaphore:
        """
        获取当前 loop 对应的 asyncio.Semaphore。
        若不存在则新建一个并缓存。
        """
        loop = self._get_current_loop()
        semaphore = self._semaphores.get(loop)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._value)
            self._semaphores[loop] = semaphore
        return semaphore

    # ---------- 公共 API，与 asyncio.Semaphore 保持尽量一致 ----------

    def locked(self) -> bool:
        """
        返回当前 loop 下的那个 semaphore 是否已被完全 acquire（即内部计数器为 0）。
        不同 loop 之间互不影响。
        """
        semaphore = self._get_semaphore_for_current_loop()
        return semaphore.locked()

    async def acquire(self) -> bool:
        """
        在当前 loop 下 acquire 对应的 asyncio.Semaphore。
        """
        semaphore = self._get_semaphore_for_current_loop()
        return await semaphore.acquire()

    def release(self) -> None:
        """
        在当前 loop 下 release 对应的 asyncio.Semaphore。
        """
        semaphore = self._get_semaphore_for_current_loop()
        semaphore.release()

    # 支持 async with 语法
    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()
