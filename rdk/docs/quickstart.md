# robot-cli v1.1 快速上手

## 安装与终端向导

需要 Python >= 3.10；在仓库 `rdk/` 下执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
robot-cli
```

裸命令进入终端菜单，可以创建项目、查看模板、新建草稿、启停、导入和记录评审发布。
创建项目时依次选择模板版本，填写名称、节点名、维护者、邮箱、许可证和 ROS 发行版等参数。
输入错误会提示重填；选择输出目录后，可初始化 Git、生成 GitHub Actions CI，并选择本地构建测试。
确认创建后执行生成；成功后自动退出。取消确认返回菜单，菜单输入 `0` 或按 Ctrl+C 退出。
构建测试失败时退出码为 1，保留项目和日志，便于修复依赖后手动重试。

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
