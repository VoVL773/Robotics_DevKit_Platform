# 快速上手：从零创建一个能跑的 ROS 2 软件包

这个案例用 `robot-cli` 创建一个 ROS 2 Python 包 `demo_pkg`，编译后运行里面的
示例节点 `hello_node`，它会每秒打印一条 `hello from demo_pkg #N`。

## 0. 环境准备

```bash
# 加载 ROS 2 Jazzy（每个新终端都要做一次）
source /opt/ros/jazzy/setup.bash

# 进入 rdk 目录，安装成可编辑模式（改代码后不用重新安装）
cd ~/VoVL773/Robotics_DevKit_Platform/rdk
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

安装成功后 `robot-cli` 命令就可以用了。

## 1. 看看有哪些模板

```bash
robot-cli template list
```

```text
名称                 版本         说明
------------------------------------------------------------
ros2-python          1.0.0        ROS 2 Python 软件包模板
ros2-cpp             1.0.0        ROS 2 C++ 软件包模板
pytorch-training     1.0.0        PyTorch 模型训练模板
```

再看某个模板的详情：

```bash
robot-cli template info ros2-python
```

## 2. 创建项目

```bash
# 先建一个工作空间，生成的包会放在 src/ 里
mkdir -p ~/demo_ws/src
robot-cli project create ros2-python --name demo_pkg --output ~/demo_ws/src
```

```text
...
creating folder /home/you/demo_ws/src/demo_pkg
...

项目创建成功：/home/you/demo_ws/src/demo_pkg

下一步：
  cd /home/you/demo_ws
  colcon build --symlink-install
  source install/setup.bash
  ros2 run demo_pkg hello_node
```

说明：`robot-cli` 内部实际执行的是

```bash
ros2 pkg create demo_pkg \
  --build-type ament_python \
  --license Apache-2.0 \
  --dependencies rclpy \
  --node-name hello_node \
  --destination-directory ~/demo_ws/src
```

生成骨架后，再把 `templates/ros2-python/` 里的示例节点覆盖进去，
所以 `demo_pkg/hello_node.py` 是一个真正会 `rclpy.spin()` 的节点。

## 3. 编译

```bash
cd ~/demo_ws
colcon build --symlink-install
```

```text
Starting >>> demo_pkg
Finished <<< demo_pkg [1.02s]

Summary: 1 package finished [1.15s]
```

## 4. 运行

```bash
source install/setup.bash
ros2 run demo_pkg hello_node
```

```text
[INFO] [1750000000.123456789] [hello_node]: hello_node 已启动，按 Ctrl+C 退出
[INFO] [1750000000.623456789] [hello_node]: hello from demo_pkg #1
[INFO] [1750000001.123456789] [hello_node]: hello from demo_pkg #2
[INFO] [1750000001.623456789] [hello_node]: hello from demo_pkg #3
```

按 `Ctrl+C` 退出。换个终端执行 `ros2 node list` 也能看到 `/hello_node`。

## 5. 改一改

`demo_pkg/demo_pkg/hello_node.py` 里改 `_on_timer` 的打印内容，因为
`--symlink-install` 不需要重新编译，直接再 `ros2 run` 就能看到效果。
