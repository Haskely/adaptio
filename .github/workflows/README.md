# 使用教程

## Publish to PyPI

### 1. 在 PyPI 和 TestPyPI 上创建带有可信发布者的项目

> https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/

需要在两个平台上分别进行配置：
1. TestPyPI: https://test.pypi.org/
2. PyPI: https://pypi.org/

在每个平台上执行以下步骤：
1. 注册并登录
2. 打开 manage/account/publishing/ 页面
3. 找到 Add a new pending publisher
4. 填写以下信息：
   - PyPI Project Name：本例为 `adaptio`
   - Owner：本例为 `Haskely`
   - Repository name：本例为 `adaptio`
   - Workflow name：本例为 `publish-to-pypi.yml`
   - Environment name：
     - TestPyPI 平台填写：`testpypi`
     - PyPI 平台填写：`pypi`
5. 点击 `ADD` 按钮

### 2. 配置仓库 Workflow

1. 新建 `.github/workflows/publish-to-pypi.yml` 文件
2. 填写文件内容，参考 [publish-to-pypi.yml](./publish-to-pypi.yml)
3. 注意修改 `PYPI_PROJECT_NAME` 为你的项目名称
4. 提交代码

### 3. 发布

1. 设置 tag，本例为 `v0.0.1`，具体执行 `git tag v0.0.1` 和 `git push origin v0.0.1`
2. 等待 Workflow 执行完成

### 4. 验证

1. 打开 https://test.pypi.org/project/adaptio/
2. 打开 https://pypi.org/project/adaptio/
