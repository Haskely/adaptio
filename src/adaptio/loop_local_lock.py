import asyncio
import weakref


class LoopLocalLock:
    """
    LoopLocalLock: 为每个 event loop 自动分配一把 asyncio.Lock。

    - 同一个 LoopLocalLock 实例，可以在多个线程 / 多个 event loop 下使用。
    - 每个 loop 拿到的都是"自己的那把 asyncio.Lock"，互相之间独立，不共享状态。
    - 主要用途：避免 asyncio.Lock 在多线程、多 loop 场景下的
      "RuntimeError: <Lock ...> is bound to a different event loop"。

    注意：
    ----
    这个类 **不是** 跨 loop / 跨线程互斥。
    它提供的是"按 loop 局部互斥"，更多是为了代码架构上的方便，避免错误。
    如果你需要跨线程全局互斥，请使用 threading.Lock。
    """

    def __init__(self) -> None:
        # key: loop (弱引用), value: asyncio.Lock (强引用)
        self._locks: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, asyncio.Lock
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
                "LoopLocalLock must be used inside an asyncio event loop "
                "(i.e., inside an `async def` function)."
            ) from None
        return loop

    def _get_lock_for_current_loop(self) -> asyncio.Lock:
        """
        获取当前 loop 对应的 asyncio.Lock。
        若不存在则新建一个并缓存。
        """
        loop = self._get_current_loop()
        lock = self._locks.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[loop] = lock
        return lock

    # ---------- 公共 API，与 asyncio.Lock 保持尽量一致 ----------

    def locked(self) -> bool:
        """
        返回当前 loop 下的那把锁是否已被 acquire。
        不同 loop 之间互不影响。
        """
        lock = self._get_lock_for_current_loop()
        return lock.locked()

    async def acquire(self) -> bool:
        """
        在当前 loop 下 acquire 对应的 asyncio.Lock。
        """
        lock = self._get_lock_for_current_loop()
        return await lock.acquire()

    def release(self) -> None:
        """
        在当前 loop 下 release 对应的 asyncio.Lock。
        """
        lock = self._get_lock_for_current_loop()
        lock.release()

    # 支持 async with 语法
    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()
