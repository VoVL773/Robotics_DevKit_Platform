# robot-cli v1.1 快速上手

## 安装与终端工作台

需要 Python >= 3.10；在仓库 `rdk/` 下执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
robot-cli
```

裸命令进入 Textual 全屏终端工作台，不需要浏览器或桌面窗口。

- **项目创建**：左侧选择模板版本，右侧表单按模板参数动态生成；支持下拉框、默认值与输入校验。
  填写生成位置后，可勾选 Git、CI、构建测试和“成功后自动退出”。创建按钮固定在底部，长表单可滚动。
- **模板管理**：用鼠标或方向键选择版本，查看维护者、依赖、环境、变更日志和参数；可新建草稿、导入、启停与记录评审发布。
  新建和导入表单可展开；模板文件仍在命令输出/详情中显示的目录编辑。
- **环境检查**：查看当前终端的系统、Python、ROS、colcon 和 PyTorch 安装状态。
- **构建日志**：生成、Git、colcon、训练和测试在独立后台进程中运行，输出实时滚动，失败后保留表单与文件。
  可以切回配置页查看参数，也可点击“取消任务”终止进程组。

按 Tab / Shift+Tab 切换焦点，Enter 操作按钮，空格勾选复选框；鼠标点击标签页、下拉框与按钮。
F5 刷新模板和环境，Ctrl+L 打开日志，Ctrl+Q 或 Ctrl+C 清理当前任务并退出。
建议终端至少 80×24，较长表单使用鼠标滚轮或键盘滚动；较宽窗口可显示更多信息。
切换前请先保存参数；刷新同一模板时会保留已填值。

“构建并执行冒烟测试”默认不勾选，依赖须预先安装。ROS 环境必须在启动界面的终端加载，
运行中的界面不会加载其他终端的环境变量；source ROS 后重新启动即可。
取消或失败后保留已生成文件，已有项目不会覆盖；若项目已生成，可进入该目录手动重试构建，
或改用新的项目名/目录。

旧版逐步问答向导可继续使用：

```bash
robot-cli --wizard
```

不支持全屏交互的终端或重定向环境请使用 `--wizard` 或子命令。
`--help` 查看所有非交互子命令，`--version` 查看 CLI 版本。

ROS 生成与构建需要 Ubuntu 24.04 + ROS 2 Jazzy。
模板管理与 PyTorch 创建不检查 ROS；`--help` 查看所有非交互子命令，`--version` 查看 CLI 版本。

## 四个 P0 模板

| 名称 | 生成内容 | 运行环境 |
| --- | --- | --- |
| `ros2-cpp` | C++17 节点、CMake、参数、Launch、gtest、文档 | Ubuntu 24.04 + Jazzy |
| `ros2-python` | Python 节点、ament 打包、参数、Launch、pytest、文档 | Ubuntu 24.04 + Jazzy |
| `ros2-bringup` | talker/listener 启动、命名空间、机器人配置、测试、文档 | Ubuntu 24.04 + Jazzy |
| `pytorch-training` | Dataset、MLP、Trainer、配置、训练、评测、测试 | Python >= 3.10 + torch >= 2.2 |

四个模板初始版本均为 `1.0.0`。`ros2-cpp-package`、`ros2-cpp-template` 是 `ros2-cpp` 的别名，
`ros2-python-package` 是 `ros2-python` 的别名。P1 Robot Application、LeRobot Policy、Isaac Lab Task、
Robot Deployment 尚未发布，不列为可用模板。

## 创建 ROS 2 C++ 项目

先安装 ROS 2 Jazzy、colcon、rosdep，以及项目的 ROS 依赖。

```bash
source /opt/ros/jazzy/setup.bash
robot-cli project create ros2-cpp-package@1.0.0 \
  --name demo_cpp --node-name demo_node \
  --maintainer 'Robot Team' --maintainer-email team@example.com \
  --license Apache-2.0 --ros-distro jazzy \
  --output ~/demo_ws/src --git --ci
cd ~/demo_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select demo_cpp
source install/setup.bash
ros2 launch demo_cpp hello.launch.py
```

节点每秒输出日志；也可以用 `ros2 run demo_cpp demo_node` 直接启动。
`config/hello.yaml` 中 `period` 是正数秒数，`message` 是日志内容；修改文件后重启节点。

```bash
colcon test --packages-select demo_cpp --event-handlers console_direct+
colcon test-result --verbose
```

Python 流程相同：将模板换成 `ros2-python@1.0.0`。
`--smoke-test` 可在生成后执行 colcon 构建、测试和结果检查；依赖必须预先安装，CLI 不自动运行 apt/rosdep。
自动化集成测试还会短时启动 Launch，确认日志或节点通信。
`--git` 只初始化本地仓库；`--ci` 只生成工作流文件，不推送到远端。

## 创建 Bringup

```bash
robot-cli project create ros2-bringup@1.0.0 --name demo_bringup --output ~/demo_ws/src
cd ~/demo_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select demo_bringup
source install/setup.bash
ros2 launch demo_bringup bringup.launch.py
```

默认在 `/demo_robot/chatter` 上由官方 `demo_nodes_cpp` 的 talker 发布 String，listener 订阅。
Launch 接受 `namespace:=robot_a` 和 `params_file:=/absolute/robot.yaml`。
本例没有仿真时钟或 TF，`use_sim_time` 默认为 false。

## 创建并运行 PyTorch 项目

不需要 source ROS。生成后进入独立项目，安装运行依赖：

```bash
robot-cli project create pytorch-training@1.0.0 --name train_demo --output ~/projects
cd ~/projects/train_demo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m training.train --config configs/default.json
python -m training.evaluate --checkpoint outputs/checkpoint.pt
python -m pytest -q
```

配置包含种子、样本数、模型维度、学习率、轮数与输出目录。CPU 训练使用合成二分类数据，
固定种子划分训练集和独立评测集，不下载数据。
`outputs/` 保存 checkpoint、训练后评测指标和再次评测指标。
checkpoint 含模型、优化器、配置和轮数；当前基础模板没有提供断点恢复或导出命令。
如果当前 Python 已安装 torch 和 pytest，也可创建时加 `--smoke-test` 运行测试、训练及评测。
