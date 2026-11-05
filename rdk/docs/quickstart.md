# robot-cli v1.1 快速上手

## 安装与终端工作台

需要 Python >= 3.10、venv 和网络。在仓库根目录运行一次：

```bash
bash setup.sh
```

脚本创建或复用 `rdk/.venv`，安装运行依赖，将 `ros-cli` 启动入口放入 `~/.local/bin`，
并自动配置 Bash 的交互/登录终端 PATH；使用 Zsh 时也配置对应的 `.zshrc` 和 `.zprofile`。
用户现有配置保留，首次修改前保存 `<原文件>.ros-cli.bak`。重复执行不会追加重复区块。
新开一个终端后，在任意工作目录输入 `ros-cli` 即可启动，不需要激活环境或进入仓库。
当前终端若尚未包含启动目录，脚本会显示立即生效的命令。

裸命令进入 Textual 全屏终端工作台，不需要浏览器或桌面窗口。

- **项目创建**：左侧先选择模板，再选择对应版本，默认选中最新的已发布且启用版本；右侧表单按版本参数动态生成，支持下拉框、默认值与输入校验。
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
帮助和常见参数错误默认用中文显示；命令及参数名保持英文，例如查询版本使用 `--version`。

ROS 模板 1.1 支持 Ubuntu 22.04 + Humble 或 Ubuntu 24.04 + Jazzy；跨发行版使用容器，见 [环境管理](environments.md)。
模板管理与 PyTorch 创建不检查 ROS；`--help` 查看所有非交互子命令，`--version` 查看 CLI 版本。

### 配置选项与开发安装

脚本可以从任何目录通过绝对路径运行。可选择 Python、虚拟环境及命令目录：

```bash
bash setup.sh --python python3.12 --venv ./rdk/.venv --bin-dir "$HOME/.local/bin"
```

已经安装 CLI、只需修复启动入口和 PATH 时，可以离线执行：

```bash
bash setup.sh --launcher-only
```

Ubuntu 缺少 venv 时先安装 `python3-venv`（非默认 Python 可能需要对应版本的 venv 包）。
同名启动入口若属于其他程序，脚本会报错并保留原文件；原先指向同一 CLI 的软链接可自动迁移。
支持 Bash/Zsh；Fish 等其他终端需自行把命令目录加入 PATH。
相对输出路径以启动时的当前目录为准。仓库和 `.venv` 需保留在原位置；移动后重新创建环境并运行配置脚本。

开发者需要测试依赖时，在仓库根目录执行：

```bash
rdk/.venv/bin/python -m pip install -e './rdk[dev]' wheel
rdk/.venv/bin/python -m pytest -q rdk/tests
```

`ros-cli` 支持 `--help`、`--wizard` 和全部现有子命令。
`robot-cli` 是同一程序的另一个安装入口，可在虚拟环境内使用。

## 四个 P0 模板

| 名称 | 生成内容 | 运行环境 |
| --- | --- | --- |
| `ros2-cpp` | C++17 节点、CMake、参数、Launch、gtest、文档 | Ubuntu 22.04 + Humble / Ubuntu 24.04 + Jazzy（模板 1.1） |
| `ros2-python` | Python 节点、ament 打包、参数、Launch、pytest、文档 | Ubuntu 22.04 + Humble / Ubuntu 24.04 + Jazzy（模板 1.1） |
| `ros2-bringup` | talker/listener 启动、命名空间、机器人配置、测试、文档 | Ubuntu 22.04 + Humble / Ubuntu 24.04 + Jazzy（模板 1.1） |
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
