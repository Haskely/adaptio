# Adaptio

Adaptio 是一个基于 Python asyncio 的智能并发控制工具。它借鉴了 TCP 拥塞控制算法的思想，可以根据系统负载动态调整并发任务的数量，从而优化任务吞吐量并防止过载。此外，还提供了一个装饰器，当任务因系统过载失败时自动重试。

## 特性

- 🚀 动态并发控制 - 自动调整工作协程数量
- 🛡️ 过载保护 - 内置过载检测和处理机制
- 📈 自适应调节 - 借鉴 TCP 拥塞控制算法实现平滑调节
- 🔄 自动重试 - 提供装饰器支持任务重试
- 🎯 简单易用 - 提供直观的 API 接口

## 安装

```bash
python3.10 -m venv .venv --prompt adaptio
source .venv/bin/activate
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
- overload_exception（可选）：当 scheduler 为 None 时检测的过载异常，默认为 ServiceOverloadError。
- log_level（可选）：当 scheduler 为 None 时使用的日志级别，默认为 "INFO"。
- log_prefix（可选）：当 scheduler 为 None 时使用的日志前缀，默认为 ""。

使用方法

以下是如何使用 with_adaptive_retry 装饰器的示例：

```python
from adaptio import with_adaptive_retry, ServiceOverloadError
import asyncio
import random

# 设计一个达到 32 并发就会触发 ServiceOverloadError 的测试任务
sample_task_overload_threshold = 32
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
async def sample_task_with_shared_scheduler():
    # 混合运行不同类型的任务，它们会共享并发限制
    tasks = []
    for i in range(500):
        if i % 2 == 0:
            tasks.append(task_type_a(i))
        else:
            tasks.append(task_type_b(i))

    for result in asyncio.as_completed(tasks):
        try:
            print(await result)
        except Exception as e:
            print(f"任务失败: {e}")

if __name__ == "__main__":
    asyncio.run(sample_task_with_shared_scheduler())
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

## 异步控制装饰器：with_async_control

该装饰器提供了全面的异步操作控制方案，支持并发数限制、QPS控制和重试机制。

装饰器参数：

- exception_type：要捕获的异常类型，默认为 Exception
- max_concurrency：最大并发数，默认为 0（不限制）
- max_qps：每秒最大请求数，默认为 0（不限制）
- retry_n：重试次数，默认为 3 次
- retry_delay：重试间隔时间（秒），默认为 1.0 秒
- raise_after_retry：重试失败后是否抛出异常，默认为 False

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
git tag v0.1.0
git push origin v0.1.0
```

2. CI/CD 将自动：
   - 运行测试
   - 构建包
   - 发布到 PyPI
