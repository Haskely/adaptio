# Adaptio

> An intelligent adaptive asynchronous concurrency control library that makes your Python async tasks run more stably and efficiently

[![PyPI version](https://badge.fury.io/py/adaptio.svg)](https://badge.fury.io/py/adaptio)
[![Python Version](https://img.shields.io/pypi/pyversions/adaptio.svg)](https://pypi.org/project/adaptio/)
[![License](https://img.shields.io/github/license/Haskely/adaptio.svg)](https://github.com/Haskely/adaptio/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/badge/adaptio)](https://pepy.tech/project/adaptio)
[![GitHub Stars](https://img.shields.io/github/stars/Haskely/adaptio.svg)](https://github.com/Haskely/adaptio/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/Haskely/adaptio.svg)](https://github.com/Haskely/adaptio/issues)
[![Dependencies](https://img.shields.io/librariesio/github/Haskely/adaptio)](https://libraries.io/github/Haskely/adaptio)

[中文文档](README_ZH.md)

Adaptio is an intelligent concurrency control tool based on Python asyncio. It draws inspiration from TCP congestion control algorithms to dynamically adjust the number of concurrent tasks based on system load, optimizing task throughput and preventing overload. Additionally, it provides a decorator for automatic retry of tasks that fail due to system overload.

## Features

- 🚀 Dynamic Concurrency Control - Automatically adjusts the number of worker coroutines
- 🛡️ Overload Protection - Built-in overload detection and handling mechanisms
- 📈 Adaptive Adjustment - Implements smooth adjustment inspired by TCP congestion control algorithms
- 🔄 Automatic Retry - Provides decorator support for task retry
- 🎯 Easy to Use - Offers intuitive API interface

## Installation

Install the latest stable version from PyPI:

```bash
pip install adaptio
```

## Quick Start

The library provides an adaptive retry decorator: `with_adaptive_retry`

This decorator can be used to automatically retry tasks that fail due to system overload (ServiceOverloadError).

Decorator Parameters:

- scheduler (optional): AdaptiveAsyncConcurrencyLimiter instance, defaults to None. If None, creates an independent scheduler for each decorated function.
- max_retries (optional): Maximum number of retries, defaults to 1024.
- retry_interval_seconds (optional): Interval between retries in seconds, defaults to 1 second.
- max_concurrency (optional): Maximum concurrency when scheduler is None, defaults to 256.
- min_concurrency (optional): Minimum concurrency when scheduler is None, defaults to 1.
- initial_concurrency (optional): Initial concurrency when scheduler is None, defaults to 1.
- adjust_overload_rate (optional): Overload adjustment rate when scheduler is None, defaults to 0.1.
    - This means that if the number of calls triggering overload errors exceeds this ratio in the recent round of concurrent calls, the concurrency will be reduced
- overload_exception (optional): Overload exception to detect when scheduler is None, defaults to ServiceOverloadError.
- log_level (optional): Log level when scheduler is None, defaults to "INFO".
- log_prefix (optional): Log prefix when scheduler is None, defaults to "".
- ignore_loop_bound_exception (optional): Whether to ignore event loop binding exceptions, defaults to False.
  - An exception is raised when a semaphore is initialized in one event loop but used in another
  - When set to True, this exception will be ignored, but the semaphore will lose its concurrency limiting capability
  - Only used in special scenarios, typically when calling async functions in a multi-threaded environment

Usage Example:

```python
from adaptio import with_adaptive_retry, ServiceOverloadError
import asyncio
import random

# Design a test task that triggers ServiceOverloadError at 16 concurrency
sample_task_overload_threshold = 16
sample_task_running_count = 0

async def sample_task(task_id):
    """A sample task that simulates workload and triggers overload at a certain concurrency."""
    global sample_task_running_count
    sample_task_running_count += 1
    # Simulate random task duration
    await asyncio.sleep(random.uniform(1, 3))
    # Simulate overload error
    if sample_task_running_count > sample_task_overload_threshold:
        sample_task_running_count -= 1
        raise ServiceOverloadError(
            f"Service overloaded with {sample_task_running_count} tasks > {sample_task_overload_threshold}"
        )
    else:
        sample_task_running_count -= 1
    return f"Task {task_id} done"

# Method 1: Using default configuration
@with_adaptive_retry()
async def sample_task_with_retry(task_id):
    return await sample_task(task_id)

# Method 2: Custom configuration parameters
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

# Method 3: Using custom scheduler (shared between multiple functions)
# Create a shared scheduler instance
from adaptio import AdaptiveAsyncConcurrencyLimiter

shared_scheduler = AdaptiveAsyncConcurrencyLimiter(
    max_concurrency=64,
    min_concurrency=2,
    initial_concurrency=4,
    adjust_overload_rate=0.15
)

# Multiple functions sharing the same scheduler
@with_adaptive_retry(scheduler=shared_scheduler)
async def task_type_a(task_id):
    return await sample_task(task_id)

@with_adaptive_retry(scheduler=shared_scheduler)
async def task_type_b(task_id):
    return await sample_task(task_id)

# Run example tasks
async def main():
    print("=== Testing Method 1: Using default configuration ===")
    tasks1 = [sample_task_with_retry(i) for i in range(100)]
    for result in asyncio.as_completed(tasks1):
        try:
            print(await result)
        except Exception as e:
            print(f"Task failed: {e}")

    print("\n=== Testing Method 2: Using custom configuration ===")
    tasks2 = [sample_task_with_custom_retry(i) for i in range(100)]
    for result in asyncio.as_completed(tasks2):
        try:
            print(await result)
        except Exception as e:
            print(f"Task failed: {e}")

    print("\n=== Testing Method 3: Using shared scheduler ===")
    # Mix different types of tasks, they will share concurrency limits
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
            print(f"Task failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

Explanation:

- Automatic Retry: Tasks are automatically retried when they fail due to ServiceOverloadError
- Configuration Methods: The example shows three different configuration methods:
  1. Using default configuration (independent scheduler per function)
  2. Custom configuration through decorator parameters (independent scheduler per function)
  3. Using a custom scheduler instance
     - Allows multiple different functions to share the same scheduler
     - Functions sharing the scheduler are subject to shared concurrency limits
     - Suitable for scenarios requiring unified management of resource usage across multiple related functions
- Task Management: The scheduler automatically adjusts concurrency based on system load to avoid continuous overload

Usage Recommendations:

- If multiple functions access the same resources (like the same API or database), it's recommended to use a shared scheduler for unified concurrency management
- If functions are completely independent, you can use default configuration or independent custom configuration
- Shared schedulers can more precisely control overall system load and prevent resource overuse

## Decorating aiohttp Request Functions

The `raise_on_aiohttp_overload` decorator is used to convert specific HTTP status codes from aiohttp into ServiceOverloadError exceptions, making it easier to integrate with dynamic task schedulers.

Decorator Parameters:
- overload_status_codes (optional): List of HTTP status codes to convert to overload exceptions, defaults to (503, 429)

Usage Example:

```python
from adaptio import with_adaptive_retry, raise_on_aiohttp_overload
import aiohttp

@with_adaptive_retry()
@raise_on_aiohttp_overload()
async def fetch_data(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()

# Combined usage example
async def main(data_id: str):
    async with aiohttp.ClientSession() as session:
        try:
            data = await fetch_data(session, f"http://api.example.com/data/{data_id}")
            print(f"Data retrieved successfully: {data}")
        except Exception as e:
            print(f"Failed to retrieve data: {data_id=} {e}")

if __name__ == "__main__":
    asyncio.run(asyncio.gather(*(main(data_id) for data_id in range(100))))
```

Notes:
- When a request returns 503 (Service Unavailable) or 429 (Too Many Requests) status codes, the decorator converts them to ServiceOverloadError
- Can be combined with the with_adaptive_retry decorator for automatic retry functionality
- Supports customizing the list of status codes to convert

Usage Recommendations:
- It's recommended to combine this decorator with with_adaptive_retry for complete overload handling
- You can customize the overload status codes based on the target API's characteristics
- The order of decorators is important, raise_on_aiohttp_overload should be the inner decorator

## Async Control Decorator: with_async_control

This decorator provides a comprehensive async operation control solution, supporting concurrency limits, QPS control, and retry mechanisms.

Decorator Parameters:

- exception_type: Exception type to catch, defaults to Exception
- max_concurrency: Maximum concurrency, defaults to 0 (no limit)
- max_qps: Maximum requests per second, defaults to 0 (no limit)
- retry_n: Number of retries, defaults to 3
- retry_delay: Retry interval in seconds, defaults to 1.0

Usage Example:

```python
from adaptio import with_async_control
import asyncio

@with_async_control(
    exception_type=ValueError,  # Only catch ValueError
    max_concurrency=5,    # Maximum 5 concurrent tasks
    max_qps=10,       # Maximum 10 requests per second
    retry_n=2,        # Retry 2 times after failure
    retry_delay=0.5   # Retry interval 0.5 seconds
)
async def api_call(i: int) -> str:
    # Simulate API call
    await asyncio.sleep(1.0)
    return f"Request {i} successful"

async def main():
    # Create multiple concurrent tasks
    tasks = [api_call(i) for i in range(10)]

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results):
        print(f"Task {i}: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

Usage Scenarios:

- API Call Rate Limiting: Control request frequency to external services
- Resource Access Control: Limit concurrent access to databases or other shared resources
- Simple Retry Requirements: Handle temporary failure scenarios

Differences from with_adaptive_retry:

- with_async_control is more suitable for fixed concurrency control scenarios
- with_adaptive_retry provides dynamic load adaptation capabilities
- Choose the appropriate decorator based on actual requirements

## Development Guide

### Environment Setup

1. Clone the repository and create a virtual environment:
```bash
git clone https://github.com/Haskely/adaptio.git
cd adaptio
python3.10 -m venv .venv --prompt adaptio
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

2. Install development dependencies:
```bash
pip install -e ".[dev]"
pre-commit install
```

### Code Standards

This project uses multiple tools to ensure code quality:

1. Ruff: For code formatting and linting
   - Auto-fix: `ruff check --fix .`
   - Format: `ruff format .`

2. MyPy: For static type checking
   - The project enables strict type checking, including:
     - Prohibiting untyped function definitions
     - Prohibiting incomplete function definitions
     - Prohibiting untyped decorators
     - Enforcing explicit optional type declarations
   - Run checks: `mypy .`

3. Pre-commit hooks:
   - Automatically run the following checks before commit:
     - Ruff checks and formatting
     - MyPy type checking
     - Trailing whitespace check
     - File end newline check
     - Unit tests

### Testing

Run unit tests:
```bash
python -m unittest discover tests
```

### Type Hints

This project fully supports type hints and includes a `py.typed` marker file. Users can get complete type checking support in their projects.

Example:
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

### Releasing a New Version

1. Update version number (using git tag):
```bash
cz bump
git push
git push --tags
```

2. CI/CD will automatically:
   - Run tests
   - Build package
   - Publish to PyPI

## FAQ

### Q: How to choose the appropriate initial concurrency?
A: It's recommended to start with a small value (like 4-8) and let the system automatically adjust to the optimal value. Too large an initial value may cause system overload at startup.

### Q: Usage scenarios for different decorators?
A:
- `with_adaptive_retry`: Suitable for scenarios requiring dynamic concurrency adjustment, especially when load varies significantly
- `with_async_control`: Suitable for scenarios requiring fixed concurrency limits and QPS control
- `raise_on_aiohttp_overload`: Specifically for handling HTTP request overload situations

### Q: How to monitor system runtime status?
A: You can view detailed adjustment process by setting `log_level="DEBUG"`, or directly access scheduler properties like `current_concurrency` to get runtime status.

### Q: When to use the `ignore_loop_bound_exception` parameter?
A: This parameter is mainly used to handle special cases when using async code in a multi-threaded environment. If you initialize a semaphore in one thread and then use it in an async function in another thread, you might encounter the "is bound to a different event loop" error. Usually, this indicates a design issue in the code, and the async/sync interaction logic should be fixed. However, in some unavoidable cases, you can set this parameter to True to ignore the exception, but note that this will cause concurrency control to fail. Most applications don't need to set this parameter.
