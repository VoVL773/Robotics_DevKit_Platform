# Robotics DevKit Platform

维护者：**VoVL773**。

面向机器人与具身智能研发的工程工具平台。当前交付 **robot-cli v1.1 终端版**：
Textual 全屏终端工作台、版本化模板管理，以及 ROS 2 C++、ROS 2 Python、ROS 2 Bringup、PyTorch Training 四个 P0 模板。

```bash
bash setup.sh
```

脚本会准备虚拟环境、安装 CLI、配置启动入口与 Bash/Zsh 的 PATH，无需 sudo。
需要 Python 3.10+、venv 和安装依赖所需的网络。配置完成后，新开终端，在任意目录输入：

```bash
ros-cli
```

无需进入仓库或激活虚拟环境。`ros-cli` 与 `robot-cli` 支持相同的参数和子命令，
配置详情与开发安装方式见[快速上手](rdk/docs/quickstart.md)。

不带参数进入可点击的全屏终端界面，提供“项目创建 / 模板管理 / 环境检查 / 构建日志”四个页面。
创建项目时先选择模板，再选择对应版本；默认选择该模板最新的已发布且启用版本。
支持鼠标、Tab 切换焦点、F5 刷新和 Ctrl+Q 退出；任务在后台执行，可查看实时日志并取消。
默认成功后自动退出，也可在表单中取消勾选，留在界面查看结果。
旧版逐步问答向导保留为 `robot-cli --wizard`。
也可以使用子命令编写脚本：

```bash
robot-cli template list
robot-cli template info ros2-cpp-package@1.0.0
source /opt/ros/jazzy/setup.bash
robot-cli project create ros2-cpp-package@1.0.0 \
  --name demo_cpp --node-name demo_node --maintainer 'Team' \
  --output ~/demo_ws/src --git --ci --smoke-test
```

ROS 模板 1.1 支持 Ubuntu 22.04 + Humble、Ubuntu 24.04 + Jazzy；本机不匹配时提示选择已有容器或新建容器，填写名称和挂载目录。模板管理与 PyTorch 项目创建无需 ROS。
PyTorch 示例在 CPU 上运行，无需下载数据。桌面图形界面及 P1 模板留待后续实现。

- [快速上手](rdk/docs/quickstart.md)：向导、项目创建、构建与训练。
- [模板管理](rdk/docs/template-management.md)：版本、参数、启停、评审与 Git/注册表导入。
- [环境管理](rdk/docs/environments.md)：doctor、CPU 容器、Dev Container、依赖锁与可选 GPU。
- [目录结构](rdk/docs/dir_intro.md)：源码、资源与测试。
- [验证记录](rdk/docs/verification.md)：本地验证范围与执行方法。
- [任务要求](任务要求.md)和[实施路线](实施方案与开发路线.md)：阶段规划；其中早期现状描述是历史基线，当前功能以本 README 为准。

环境管理（默认 CPU，GPU 按需选择）：

```bash
robot-cli env list
robot-cli env doctor
robot-cli env containers ros2-humble-dev
robot-cli env init all --workspace .
robot-cli env shell ros2-humble-dev
```

所有模板均支持 **生成示例代码**（默认）/ **不生成示例代码**，可在项目创建页或向导选择；CLI 使用 `--examples` / `--no-examples`。无示例模式仅生成工程骨架，不运行演示任务，详见 [选项说明](rdk/docs/quickstart.md#选择是否生成示例代码)。

公共模板统一位于 [`templates/`](templates/README.md)，与 CLI 源码分开维护、独立打包。
