# Robotics DevKit Platform

面向机器人与具身智能研发的工程工具平台。当前交付 **robot-cli v1.1 终端版**：
交互式项目向导、版本化模板管理，以及 ROS 2 C++、ROS 2 Python、ROS 2 Bringup、PyTorch Training 四个 P0 模板。

```bash
cd rdk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
robot-cli
```

不带参数进入终端菜单；创建成功、可选构建测试完成后自动退出。
也可以使用子命令编写脚本：

```bash
robot-cli template list
robot-cli template info ros2-cpp-package@1.0.0
source /opt/ros/jazzy/setup.bash
robot-cli project create ros2-cpp-package@1.0.0 \
  --name demo_cpp --node-name demo_node --maintainer 'Team' \
  --output ~/demo_ws/src --git --ci --smoke-test
```

ROS 模板要求 Ubuntu 24.04 + ROS 2 Jazzy；模板管理与 PyTorch 项目创建无需 ROS。
PyTorch 示例在 CPU 上运行，无需下载数据。桌面图形界面及 P1 模板留待后续实现。

- [快速上手](rdk/docs/quickstart.md)：向导、项目创建、构建与训练。
- [模板管理](rdk/docs/template-management.md)：版本、参数、启停、评审与 Git/注册表导入。
- [目录结构](rdk/docs/dir_intro.md)：源码、资源与测试。
- [验证记录](rdk/docs/verification.md)：本地验证范围与执行方法。
- [任务要求](任务要求.md)和[实施路线](实施方案与开发路线.md)：阶段规划；其中早期现状描述是历史基线，当前功能以本 README 为准。
