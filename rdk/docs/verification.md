# CLI v1.1 本地验证记录

## 原生框架报错与日志转发修复（2026-11-05）

帮助说明与业务提示保留中文，框架错误不再翻译或包装。通过与原生 Typer 对照，
验证错误文本、异常类型和退出码一致，帮助中的用户文本和默认值不会被替换。
从 `/tmp` 调用已配置的 `ros-cli --vision`，显示原生 `No such option` 与 `--version` 建议，退出码为 2。

`run_logged` 已复现并修复日志写出异常被后台线程吞掉、脱离进程组的后代占用管道导致超时返回延迟的问题。
改为同线程按块读取，回归覆盖写出/flush 失败后的进程清理、无换行实时输出、回车保留、
跨块 UTF-8 解码、非零退出及两类超时。只清理当前进程组；主动另建会话的后代不在清理范围内。

完整测试：**153 passed, 4 skipped**。针对性帮助/日志测试为 **46 passed**；
另外在临时目录使用容器锁定的 Typer 0.15.1 / Click 8.1.8 执行帮助/错误测试，**26 passed**。
`git diff --check` 通过。本轮使用真实本地子进程验证日志，未重新构建 Docker 镜像或运行 ROS 冒烟测试。

## 一键配置与任意目录启动（2026-11-05）

新增根目录 `setup.sh`，准备运行环境、用户级 `ros-cli` 入口与 Bash/Zsh PATH。
本轮完整回归：**139 passed, 4 skipped**，执行命令如下：

```bash
PYTHONDONTWRITEBYTECODE=1 rdk/.venv/bin/python -m pytest -q -p no:cacheprovider rdk/tests
```

实际使用全新 HOME 和包含中文、空格的虚拟环境路径，完成依赖安装；
从 `/tmp`、初始 PATH 仅含 `/usr/bin:/bin` 的新 Bash 中直接运行 `ros-cli`，
全屏工作台正常加载，Ctrl+Q 正常退出。版本查询与模板列表也通过。

当前用户的启动入口和终端配置已完成；再次执行 `--launcher-only` 后，
配置文件内容保持一致，每个文件只有一个 PATH 区块。原终端配置已备份。
`bash -n setup.sh` 与 `git diff --check` 通过。
本轮未重新执行 ROS/Docker 构建；下文保留此前各轮的验证记录。

验证日期：2026-11-05（Asia/Shanghai）。环境为 Ubuntu 24.04、Python 3.12、ROS 2 Jazzy，
PyTorch CPU 版本为 2.15.0+cpu。以下为实际执行结果，不代表远端 CI 已运行。

## CLI、管理和打包

在仓库根目录执行：

```bash
rdk/.venv/bin/python -m pytest -q rdk/tests
```

结果（含全屏 TUI 回归）：**77 passed, 4 skipped**。四项真实依赖冒烟测试默认跳过，已用下面的独立命令实际执行。

覆盖范围：

- 模板查看、新建、草稿评审发布、启停、固定版本和最高可用版本选择。
- 非法名称、参数类型、范围、默认值、必填项、未知与重复参数、兼容发行版校验。
- 已有项目不覆盖，版本升级/启停不修改已生成项目。
- 本地 Git + JSON 注册表导入、提交 SHA 记录、重复版本与越界/符号链接拒绝。
- 旧问答向导的参数重填、默认值、取消退出与成功后自动退出。
- Textual 工作台的默认入口、模板/参数切换、刷新保留输入、80×24 与 120×42 窗口操作。
- 通过界面实际生成独立项目、新建草稿、记录评审发布、启停与本地模板导入。
- 后台任务失败后继续操作、运行中切页、取消整个进程组、启动瞬间退出时的清理。
- 应用服务独立导入不加载 Typer/Rich/Textual，预检失败不生成目录，直接调用与 CLI 生成文件完全一致。
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

新增全屏界面也已实际执行一次“PyTorch 项目创建 → 生成项目 pytest → CPU 训练 → checkpoint 评测”，
结果成功，accuracy 同样约 0.98077。此流程发现并修复了混合 ROS 终端自动加载 Launch pytest 插件的问题，
训练模板现在仅排除无关的 ROS Launch 插件，无需安装额外 ROS Python 依赖。

TUI 通过 Textual 无头终端操作测试，并导出截图检查布局；实际终端使用 `robot-cli`，
旧问答模式改用 `robot-cli --wizard`。

## CI 与后续边界

已提供 `.github/workflows/templates.yml`，分别运行 CLI/wheel、CPU 与 ROS Jazzy 验证。
项目创建时 `--ci` 可生成独立项目的 GitHub Actions 文件。此次未推送或触发远端 CI。

本次交付终端 CLI，桌面窗口后续实现。P1 模板、身份认证审批服务、断点恢复/导出、GPU 实机认证与真实机器人验证不在此次交付范围。

## 模块拆分回归（2026-11-05）

`main.py` 从 444 行缩减为 37 行，仅保留入口装配。命令、问答、项目服务、文件渲染、
CI 内容、TUI 布局和后台进程管理分别归入对应模块，依赖方向见 `dir_intro.md`。
CLI 与 TUI 统一使用 `prepare_project`，环境模块不再依赖 Typer。

此前模块拆分后执行了完整测试（56 passed, 4 skipped）和四个真实模板冒烟（4 passed），
并通过 `compileall`、`git diff --check`。完整测试包含 wheel 安装验证及原有 TUI 布局、取消和退出回归。

## 开发环境管理验收（2026-11-05）

环境管理加入后的完整测试：**77 passed, 4 skipped**。包含 wheel 内环境资产打包、
默认 CPU 不探测 GPU、init all 只准备 CPU、双发行版校验、共享基线不解析 latest、锁篡改拒绝、
已有容器只读读取、挂载映射、TUI 环境差异提示、不同宿主机 UID/GID 等回归。

| 路线 | 实际结果 |
| --- | --- |
| `env init all` | 创建 Humble CPU 开发容器；Jazzy 宿主机合格，跳过 Jazzy 容器 |
| `env verify ros2-jazzy-dev` | 本机生成、构建、测试 C++ / Python / Bringup，全部通过 |
| `env verify ros2-humble-dev` | 最终容器内生成、构建、测试三种 ROS 包，全部通过 |
| Jazzy 完整模板冒烟 | 4 passed：三类 ROS 的 Launch/通信，以及 CPU 训练/独立评测 |
| Humble ROS 完整冒烟 | 3 passed, 1 deselected：三类 ROS 的构建、Launch/通信 |
| 新建容器的项目路由 | 自定义容器名、挂载、C++ 包生成、Git/CI、构建测试通过 |
| 复用已有容器路由 | 既有挂载路径映射、/tmp 隔离 CLI、Python 包生成和构建测试通过 |
| 真实交互终端 | 环境差异确认 → 读取候选 → 输入容器名和挂载 → 生成，通过 |
| 本机/容器 `env shell` | 分别进入 Jazzy 和 Humble；容器 whoami / 用户组解析正确 |
| 可选锁定 CPU PyTorch 镜像 | Humble / Python 3.10 / torch 2.6.0+cpu，ROS 测试、训练与评测通过 |
| 最终容器内 TUI | 80×24 无头终端启动并加载七个模板版本通过 |
| Dev Container 初始化命令 | 在最终 Humble 镜像中加载 ROS 并运行 CLI 版本命令通过；未启动 VS Code Dev Containers 扩展 |

可选 CPU 训练镜像 accuracy 为 0.9807692，loss 为 0.0425470，训练记录与加载 checkpoint 评测一致。
默认 ROS CPU 镜像不安装 PyTorch；GPU 仍是独立可选配置。
本机 GPU 为 RTX 4060 Laptop，驱动 595.99.02 满足配置下限，但 Docker 未注册 NVIDIA runtime，
当前宿主机 PyTorch 为 CPU 版；**未构建/验收 GPU 镜像，也未进行 GPU 训练或仿真器认证**。

已有 `ican-delivery` 容器的 Ubuntu 22.04 / Humble 文件和原有挂载已成功只读识别，保持停止状态。
本轮功能测试使用工具自行创建的容器，未启动或修改原有业务容器。
最终保留已验证的 Humble CPU 开发容器，其余本轮临时测试容器已清理。
实际环境锁、镜像 ID 与验收结果位于 `.robot-cli/environments/`；可选 CPU 训练的历史验收位于
`.robot-cli/training-environments/`。生成测试项目保留在忽略目录 `.robot-cli/`，不进入源码提交。

两套 CPU 基础镜像 registry digest 与 APT 事务已固定并随 wheel 分发；GPU 配置需显式生成锁并评审。
已新增双发行版 CPU 环境 CI job，本次未推送或触发远端 CI。
