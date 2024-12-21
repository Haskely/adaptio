# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 进行版本发布。

## [未发布]

### 新增
- 无

### 变更
- 无

### 修复
- 无

## [0.1.2] - 2024-03-03

### 变更
- 改进 `AdjustableSemaphore` 的任务处理测试
- 增强 CI 工作流程和并发处理
- 更新 README.md，增强文档说明和示例

## [0.1.1] - 2024-03-02

### 变更
- 重构 pre-commit 配置以使用 Python 环境
- 清理和优化 pyproject.toml 文件
- 改进 README 文档：
  - 添加安装说明
  - 添加使用示例
  - 添加常见问题解答（FAQ）部分

## [0.1.0] - 2024-03-01
- 初始版本发布
- 添加 `AdaptiveAsyncConcurrencyLimiter` 类用于动态并发控制
- 添加 `AdjustableSemaphore` 类用于可调整容量的信号量
- 添加 `with_adaptive_retry` 装饰器用于自适应重试
- 添加 `with_async_control` 装饰器用于异步控制
- 添加 `raise_on_aiohttp_overload` 装饰器用于 aiohttp 过载处理
- 添加完整的类型提示支持
- 添加单元测试覆盖
- 添加 CI/CD 工作流支持
- 添加自动发布到 PyPI 的支持
- 添加详细的使用文档和示例

[未发布]: https://github.com/Haskely/adaptio/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Haskely/adaptio/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Haskely/adaptio/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Haskely/adaptio/releases/tag/v0.1.0 