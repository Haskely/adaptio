# Adaptio

[English Documentation](README.md)

> 智能自适应的异步并发控制库，让你的Python异步任务运行更稳定、更高效

[![PyPI version](https://badge.fury.io/py/adaptio.svg)](https://badge.fury.io/py/adaptio)
[![Python Version](https://img.shields.io/pypi/pyversions/adaptio.svg)](https://pypi.org/project/adaptio/)
[![License](https://img.shields.io/github/license/Haskely/adaptio.svg)](https://github.com/Haskely/adaptio/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/badge/adaptio)](https://pepy.tech/project/adaptio)
[![GitHub Stars](https://img.shields.io/github/stars/Haskely/adaptio.svg)](https://github.com/Haskely/adaptio/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/Haskely/adaptio.svg)](https://github.com/Haskely/adaptio/issues)
[![Dependencies](https://img.shields.io/librariesio/github/Haskely/adaptio)](https://libraries.io/github/Haskely/adaptio)

Adaptio 是一个基于 Python asyncio 的智能并发控制工具。它借鉴了 TCP 拥塞控制算法的思想，可以根据系统负载动态调整并发任务的数量，从而优化任务吞吐量并防止过载。此外，还提供了一个装饰器，当任务因系统过载失败时自动重试。

## 特性

- 🚀 动态并发控制 - 自动调整工作协程数量
- 🛡️ 过载保护 - 内置过载检测和处理机制
- 📈 自适应调节 - 借鉴 TCP 拥塞控制算法实现平滑调节
- 🔄 自动重试 - 提供装饰器支持任务重试
- 🎯 简单易用 - 提供直观的 API 接口

## 安装

从 PyPI 安装最新稳定版：

```bash
pip install adaptio
```

## 快速开始

本库提供自适应重试装饰器：with_adaptive_retry

该装饰器可用于自动重试因系统过载 (ServiceOverloadError) 而失败的任务。

装饰器参数

- scheduler（可选）：AdaptiveAsyncConcurrencyLimiter 实例，默认为 None。如果为 None，则为每个装饰的函数创建独立的调度器。
- max_retries（可选）：最大重试次数，默认为 1024 次。
- retry_interval_seconds（可选）：重试之间的间隔时间（秒），默认为 1 秒。
- max_concurrency（可选）：当 scheduler 为 None 时使用的最大并发数，默认为 256。
- min_concurrency（可选）：当 scheduler 为 None 时使用的最小并发数，默认为 1。
- initial_concurrency（可选）：当 scheduler 为 None 时使用的初始并发数，默认为 1。
- adjust_overload_rate（可选）：当 scheduler 为 None 时使用的过载调整率，默认为 0.1。
    - 意思是在最近一轮并发调用中，若触发过载错误的调用数量超过这个比例，才会进行降低并发数操作
- overload_exception（可选）：当 scheduler 为 None 时检测的过载异常，默认为 ServiceOverloadError。
- log_level（可选）：当 scheduler 为 None 时使用的日志级别，默认为 "INFO"。
- log_prefix（可选）：当 scheduler 为 None 时使用的日志前缀，默认为 ""。
- ignore_loop_bound_exception（可选）：是否忽略事件循环绑定异常，默认为 False。
  - 当信号量在一个事件循环中初始化但在另一个循环中被使用时，会引发异常
  - 设置为 True 时将忽略此异常，但信号量将失去限制并发的能力
  - 仅在特殊场景下使用，通常在使用多线程调用异步函数时才会触发此类异常

使用方法

以下是如何使用 with_adaptive_retry 装饰器的示例：

```python
from adaptio import with_adaptive_retry, ServiceOverloadError
import asyncio
import random

# 设计一个达到 16 并发就会触发 ServiceOverloadError 的测试任务
sample_task_overload_threshold = 16
sample_task_running_count = 0

async def sample_task(task_id):
    """A sample task that simulates workload and triggers overload at a certain concurrency."""
    global sample_task_running_count
    sample_task_running_count += 1
    # 模拟随机任务耗时
    await asyncio.sleep(random.uniform(1, 3))
    # 模拟过载错误
    if sample_task_running_count > sample_task_overload_threshold:
        sample_task_running_count -= 1
        raise ServiceOverloadError(
            f"Service overloaded with {sample_task_running_count} tasks > {sample_task_overload_threshold}"
        )
    else:
        sample_task_running_count -= 1
    return f"Task {task_id} done"

# 方法1：使用默认配置
@with_adaptive_retry()
async def sample_task_with_retry(task_id):
    return await sample_task(task_id)

# 方法2：自定义配置参数
@with_adaptive_retry(
    max_retries=512,
    retry_interval_seconds=3,
    max_concurrency=128,
    min_concurrency=4,
    initial_concurrency=4,
    adjust_overload_rate=0.2
)
async def sample_task_with_custom_retry(task_id):
    return await sample_task(task_id)

# 方法3：使用自定义调度器（多个函数共享）
# 创建一个共享的调度器实例
from adaptio import AdaptiveAsyncConcurrencyLimiter

shared_scheduler = AdaptiveAsyncConcurrencyLimiter(
    max_concurrency=64,
    min_concurrency=2,
    initial_concurrency=4,
    adjust_overload_rate=0.15
)

# 多个函数共享同一个调度器
@with_adaptive_retry(scheduler=shared_scheduler)
async def task_type_a(task_id):
    return await sample_task(task_id)

@with_adaptive_retry(scheduler=shared_scheduler)
async def task_type_b(task_id):
    return await sample_task(task_id)

# 运行示例任务
async def main():
    print("=== 测试方法1：使用默认配置 ===")
    tasks1 = [sample_task_with_retry(i) for i in range(100)]
    for result in asyncio.as_completed(tasks1):
        try:
            print(await result)
        except Exception as e:
            print(f"任务失败: {e}")

    print("\n=== 测试方法2：使用自定义配置 ===")
    tasks2 = [sample_task_with_custom_retry(i) for i in range(100)]
    for result in asyncio.as_completed(tasks2):
        try:
            print(await result)
        except Exception as e:
            print(f"任务失败: {e}")

    print("\n=== 测试方法3：使用共享调度器 ===")
    # 混合运行不同类型的任务，它们会共享并发限制
    tasks3 = []
    for i in range(100):
        if i % 2 == 0:
            tasks3.append(task_type_a(i))
        else:
            tasks3.append(task_type_b(i))

    for result in asyncio.as_completed(tasks3):
        try:
            print(await result)
        except Exception as e:
            print(f"任务失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

解释

- 自动重试：当任务因 ServiceOverloadError 失败时会自动重试
- 配置方式：示例展示了三种不同的配置方式
  1. 使用默认配置（每个函数独立的调度器）
  2. 通过装饰器参数自定义配置（每个函数独立的调度器）
  3. 使用自定义的调度器实例
     - 可以让多个不同的函数共享同一个调度器
     - 共享调度器的函数会共同受到并发限制
     - 适用于需要统一管理多个相关函数资源使用的场景
- 任务管理：调度器会根据系统负载自动调整并发数，避免持续过载

使用建议

- 如果多个函数访问相同的资源（如同一个API或数据库），建议使用共享调度器来统一管理并发
- 如果函数之间完全独立，可以使用默认配置或独立的自定义配置
- 共享调度器可以更精确地控制整体系统负载，避免资源过度使用

## 异步生成器支持

`with_adaptive_retry` 装饰器现已支持异步生成器！装饰器会自动检测函数类型并提供相应的并发控制和重试机制。

### 基本用法

```python
from adaptio import with_adaptive_retry, ServiceOverloadError
import aiohttp

# ✅ 同一个装饰器，自动适配普通异步函数
@with_adaptive_retry(initial_concurrency=10)
async def fetch_one_page(url: str) -> dict:
    """获取单个页面"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 429:
                raise ServiceOverloadError("Rate limited")
            return await response.json()

# ✅ 同一个装饰器，自动适配异步生成器
@with_adaptive_retry(initial_concurrency=5)
async def fetch_all_pages(base_url: str):
    """流式获取所有分页数据"""
    async with aiohttp.ClientSession() as session:
        page = 1
        while True:
            url = f"{base_url}?page={page}"
            async with session.get(url) as response:
                if response.status == 429:
                    raise ServiceOverloadError("Rate limited")

                data = await response.json()
                if not data:
                    break

                for item in data:
                    yield item

                page += 1

# 使用方式完全一致
async def main():
    # 使用普通函数
    result = await fetch_one_page("https://api.example.com/data")
    print(result)

    # 使用生成器
    async for item in fetch_all_pages("https://api.example.com/items"):
        print(item)
```

### 重要提示

⚠️ **数据重复风险**：当生成器在部分执行后失败并重试时，会重新执行整个生成器，可能导致已产出的数据被重复产出。请确保：

1. 生成器的执行是幂等的，或
2. 消费者能够处理重复数据，或
3. 使用去重机制

### 适用场景

✅ **推荐使用**：
- 分页 API 爬取
- 数据库批量查询（每批独立）
- 文件批量处理
- 流式数据转换

❌ **不推荐使用**：
- 长时间运行的实时流（如 WebSocket）
- 有状态的数据流处理
- 需要事务保证的场景


### `with_async_control` 的异步生成器支持

`with_async_control` 装饰器同样支持异步生成器！它会自动检测函数类型并提供相应的并发控制、QPS 限制和重试功能。

```python
from adaptio import with_async_control

# ✅ 装饰异步生成器
@with_async_control(
    max_concurrency=3,
    max_qps=5,
    retry_n=2,
    cared_exception=ValueError
)
async def fetch_paginated_data(base_url: str):
    """流式获取分页数据，带并发和QPS控制"""
    page = 1
    while True:
        # 模拟 API 调用
        data = await fetch_page(f"{base_url}?page={page}")
        if not data:
            break

        for item in data:
            yield item

        page += 1

# 使用
async def main():
    async for item in fetch_paginated_data("https://api.example.com/items"):
        print(item)
```

查看 `tests/test_with_async_control_generator.py` 获取更多使用示例。

### 更多示例

查看 `examples/async_generator_examples.py` 获取更多使用示例。


## 装饰 aiohttp 请求函数

raise_on_aiohttp_overload 装饰器用于将 aiohttp 的特定HTTP状态码转换为 ServiceOverloadError 异常,便于与动态任务调度器集成。

装饰器参数:
- overload_status_codes (可选): 要转换为过载异常的HTTP状态码列表,默认为 (503, 429)

使用示例:

```python
from adaptio import with_adaptive_retry, raise_on_aiohttp_overload
import aiohttp

@with_adaptive_retry()
@raise_on_aiohttp_overload()
async def fetch_data(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()

# 组合使用示例
async def main(data_id: str):
    async with aiohttp.ClientSession() as session:
        try:
            data = await fetch_data(session, f"http://api.example.com/data/{data_id}")
            print(f"获取数据成功: {data}")
        except Exception as e:
            print(f"获取数据失败: {data_id=} {e}")

if __name__ == "__main__":
    asyncio.run(asyncio.gather(*(main(data_id) for data_id in range(100))))
```

说明:
- 当请求返回 503(Service Unavailable) 或 429(Too Many Requests) 状态码时,装饰器会将其转换为 ServiceOverloadError
- 可以与 with_adaptive_retry 装饰器组合使用,实现自动重试功能
- 支持自定义需要转换的状态码列表

使用建议:
- 建议将此装饰器与 with_adaptive_retry 组合使用,以实现完整的过载处理
- 可以根据目标 API 的特点自定义过载状态码
- 装饰器的顺序很重要,raise_on_aiohttp_overload 应该在内层

## 装饰器与 staticmethod/classmethod 的兼容性

所有 adaptio 提供的装饰器现已完全支持与 `@staticmethod` 和 `@classmethod` 组合使用，并且**兼容两种装饰器顺序**！

### 支持的装饰器

- ✅ `raise_on_overload` - 过载关键词检测
- ✅ `raise_on_aiohttp_overload` - HTTP 状态码检测
- ✅ `with_async_control` - 并发和重试控制
- ✅ `with_adaptive_retry` - 自适应重试

### 使用示例

```python
from adaptio import raise_on_overload, with_async_control

class APIClient:
    # ✅ 推荐方式：@staticmethod 在上，装饰器在下
    @staticmethod
    @raise_on_overload()
    async def fetch_data(url: str):
        # ... 实现 ...
        pass

    # ✅ 也支持：装饰器在上，@staticmethod 在下
    @raise_on_overload()
    @staticmethod
    async def fetch_data_alt(url: str):
        # ... 实现 ...
        pass

    # ✅ classmethod 同样支持
    @classmethod
    @with_async_control(max_concurrency=5)
    async def batch_fetch(cls, urls: list):
        # ... 实现 ...
        pass

    # ✅ 异步生成器也完全支持
    @staticmethod
    @raise_on_overload()
    async def stream_data(count: int):
        for i in range(count):
            yield i
```

### 实现原理

装饰器会自动检测并处理 `staticmethod` 和 `classmethod`：
1. 使用 `func.__func__` 提取被包装的原始函数
2. 对原始函数进行处理（异常转换、重试等）
3. 重新应用 `staticmethod` 或 `classmethod` 装饰

这确保了无论装饰器顺序如何，都能正常工作。

### 使用建议

- **推荐顺序**：`@staticmethod/@classmethod` 在上，其他装饰器在下（更符合直觉）
- **也支持**：其他装饰器在上，`@staticmethod/@classmethod` 在下（完全兼容）
- 两种顺序在功能上完全等价，选择你喜欢的方式即可

## 异步控制装饰器：with_async_control

该装饰器提供了全面的异步操作控制方案，支持并发数限制、QPS控制和重试机制。

装饰器参数：

- exception_type：要捕获的异常类型，默认为 Exception
- max_concurrency：最大并发数，默认为 0（不限制）
- max_qps：每秒最大请求数，默认为 0（不限制）
- retry_n：重试次数，默认为 3 次
- retry_delay：重试间隔时间（秒），默认为 1.0 秒

使用示例：

```python
from adaptio import with_async_control
import asyncio

@with_async_control(
    exception_type=ValueError,  # 只捕获 ValueError
    max_concurrency=5,    # 最多5个并发
    max_qps=10,       # 每秒最多10个请求
    retry_n=2,        # 失败后重试2次
    retry_delay=0.5   # 重试间隔0.5秒
)
async def api_call(i: int) -> str:
    # 模拟API调用
    await asyncio.sleep(1.0)
    return f"请求 {i} 成功"

async def main():
    # 创建多个并发任务
    tasks = [api_call(i) for i in range(10)]

    # 等待所有任务完成
    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results):
        print(f"任务 {i}: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

使用场景：

- API调用限流：控制对外部服务的请求频率
- 资源访问控制：限制对数据库或其他共享资源的并发访问
- 简单重试需求：处理临时性故障的场景

与 with_adaptive_retry 的区别：

- with_async_control 更适合固定的并发控制场景
- with_adaptive_retry 提供动态的负载自适应能力
- 根据实际需求选择合适的装饰器

## 开发指南

### 环境设置

1. 克隆仓库并创建虚拟环境：
```bash
git clone https://github.com/Haskely/adaptio.git
cd adaptio
python3.10 -m venv .venv --prompt adaptio
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

2. 安装开发依赖：
```bash
pip install -e ".[dev]"
pre-commit install
```

### 代码规范

本项目使用多个工具确保代码质量：

1. Ruff：用于代码格式化和 lint
   - 自动修复：`ruff check --fix .`
   - 格式化：`ruff format .`

2. MyPy：用于静态类型检查
   - 本项目启用了严格的类型检查，包括：
     - 禁止未类型化的函数定义
     - 禁止未完成的函数定义
     - 禁止未类型化的装饰器
     - 强制可选类型显式声明
   - 运行检查：`mypy .`

3. Pre-commit hooks：
   - 提交前自动运行以下检查：
     - Ruff 检查和格式化
     - MyPy 类型检查
     - 尾随空格检查
     - 文件结尾空行检查
     - 单元测试

### 测试

运行单元测试：
```bash
python -m unittest discover tests
```

### 类型提示

本项目完全支持类型提示，并包含 `py.typed` 标记文件。使用者可以在他们的项目中获得完整的类型检查支持。

示例：
```python
from adaptio import AdaptiveAsyncConcurrencyLimiter
from typing import AsyncIterator

async def process_items(items: AsyncIterator[str]) -> None:
    scheduler = AdaptiveAsyncConcurrencyLimiter(
        max_concurrency=10,
        min_concurrency=1
    )
    async for item in items:
        await scheduler.submit(process_item(item))
```

### 发布新版本

1. 更新版本号（使用 git tag）：
```bash
cz bump
git push
git push --tags
```

2. CI/CD 将自动：
   - 运行测试
   - 构建包
   - 发布到 PyPI

## 常见问题

### Q: 如何选择合适的初始并发数？
A: 建议从较小的值开始（如4-8），让系统自动调节到最优值。过大的初始值可能导致系统启动时出现过载。

### Q: 不同装饰器的使用场景？
A:
- `with_adaptive_retry`: 适合需要动态调节并发的场景，特别是负载变化较大的情况
- `with_async_control`: 适合需要固定并发限制和QPS控制的场景
- `raise_on_aiohttp_overload`: 专门用于处理HTTP请求的过载情况

### Q: 如何监控系统运行状态？
A: 可以通过设置 `log_level="DEBUG"` 来查看详细的调节过程，或者直接访问调度器的属性如 `current_concurrency` 获取运行时状态。

### Q: 什么情况下需要使用 `ignore_loop_bound_exception` 参数？
A: 这个参数主要用于处理在多线程环境中使用异步代码的特殊情况。如果你在一个线程中初始化信号量，然后在另一个线程中的异步函数中使用它，可能会遇到"is bound to a different event loop"的错误。通常情况下，这表明代码设计有问题，应该修复异步/同步交互的逻辑。但在某些无法避免的情况下，可以设置该参数为 True 来忽略异常，但需要注意这会导致并发控制失效。大多数应用不需要设置此参数。
