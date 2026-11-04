# Robotics DevKit Platform

面向机器人与具身智能研发的工程工具平台。当前交付 **robot-cli v1.1 终端版**：
Textual 全屏终端工作台、版本化模板管理，以及 ROS 2 C++、ROS 2 Python、ROS 2 Bringup、PyTorch Training 四个 P0 模板。

```bash
cd rdk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
robot-cli
```

不带参数进入可点击的全屏终端界面，提供“项目创建 / 模板管理 / 环境检查 / 构建日志”四个页面。
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
