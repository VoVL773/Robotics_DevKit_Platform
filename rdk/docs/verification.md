# CLI v1.1 本地验证记录

验证日期：2026-11-04（Asia/Shanghai）。环境为 Ubuntu 24.04、Python 3.12、ROS 2 Jazzy，
PyTorch CPU 版本为 2.15.0+cpu。以下为实际执行结果，不代表远端 CI 已运行。

## CLI、管理和打包

在仓库根目录执行：

```bash
rdk/.venv/bin/python -m pytest -q rdk/tests
```

结果：**37 passed, 4 skipped**。四项真实依赖冒烟测试默认跳过，已用下面的独立命令实际执行。

覆盖范围：

- 模板查看、新建、草稿评审发布、启停、固定版本和最高可用版本选择。
- 非法名称、参数类型、范围、默认值、必填项、未知与重复参数、兼容发行版校验。
- 已有项目不覆盖，版本升级/启停不修改已生成项目。
- 本地 Git + JSON 注册表导入、提交 SHA 记录、重复版本与越界/符号链接拒绝。
- 终端向导的参数重填、默认值、取消退出与成功后自动退出。
- wheel 在仓库外安装，读取全部四种模板，渲染与 Python 语法检查，并通过安装后的 CLI 创建项目。

未对真实团队私有 Git 服务和线上 HTTP 注册表做联通验证；相关 URL、认证和权限需由团队环境提供。

## 四个 P0 模板真实冒烟

```bash
source /opt/ros/jazzy/setup.bash
ROBOT_CLI_RUN_SMOKE=1 rdk/.venv/bin/python -m pytest -q rdk/tests/test_smoke.py
```

结果：**4 passed**。

| 模板 | 实际验证 |
| --- | --- |
| ROS 2 Python | 自定义节点名生成、colcon build/test、计时回调与非法 period 测试、Launch 日志 |
| ROS 2 C++ | C++17 编译、gtest 计时回调与非法 period、安装后 Launch 日志 |
| ROS 2 Bringup | 构建、配置/Launch 测试、实际 talker → listener 消息通信 |
| PyTorch Training | 清除 ROS 环境变量后创建、生成项目 pytest、CPU 训练、加载 checkpoint 独立评测 |

ROS 集成测试需要正常的本机 DDS socket 权限。在受限沙箱中 Bringup 因 socket 被禁止无法通信，
放开本机通信权限后上述四项全部通过。

默认 CPU 示例的评测集为 52 条合成样本：accuracy 约 **0.98077**，loss 约 **0.04255**。
训练后保存的指标与重新加载 checkpoint 评测得到的指标一致。
该结果只验证示例流程，不是机器人真实任务精度评测。

## CI 与后续边界

已提供 `.github/workflows/templates.yml`，分别运行 CLI/wheel、CPU 与 ROS Jazzy 验证。
项目创建时 `--ci` 可生成独立项目的 GitHub Actions 文件。此次未推送或触发远端 CI。

本次交付终端 CLI，桌面窗口后续实现。P1 模板、身份认证审批服务、断点恢复/导出、GPU 与真实机器人验证不在此次交付范围。
