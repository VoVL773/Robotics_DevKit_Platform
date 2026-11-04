# {{package_name}}

ROS 2 Jazzy {{language}} 示例，由 {{template_id}}@{{template_version}} 生成。
维护者：{{maintainer}}；许可证：{{license}}。

## 构建、运行和测试

在 Ubuntu 24.04 中安装 ROS 2 Jazzy 和 colcon，加载环境后，将此目录放在工作空间 src/ 下。
生成目录包含全部源代码，无需保留 robot-cli 或原始模板仓库。

```bash
source /opt/ros/jazzy/setup.bash
cd ~/demo_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select {{package_name}}
source install/setup.bash
ros2 run {{package_name}} {{node_name}}
```

也可以通过 Launch 加载 `config/hello.yaml`：

```bash
ros2 launch {{package_name}} hello.launch.py
```

节点每秒输出一条日志。`message` 为日志内容，`period` 为正数秒数；修改参数后重启节点。
直接运行时可使用 `--ros-args -p period:=0.5 -p message:=hello`。按 Ctrl+C 退出。
这是日志演示节点，不发布 Topic、Service、Action 或 TF。

```bash
colcon test --packages-select {{package_name}} --event-handlers console_direct+
colcon test-result --verbose
```

测试验证节点计时回调或参数约束；实际运行请确认日志持续输出。
