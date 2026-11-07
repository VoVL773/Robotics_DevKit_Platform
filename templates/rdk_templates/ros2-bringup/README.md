# {{package_name}}

ROS 2 Jazzy 多节点启动包，由 {{template_id}}@{{template_version}} 生成。
维护者：{{maintainer}}；许可证：{{license}}。
生成包独立构建，无需原始模板仓库；运行依赖 ROS 官方 `demo_nodes_cpp`。

```bash
source /opt/ros/jazzy/setup.bash
cd ~/demo_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select {{package_name}}
source install/setup.bash
ros2 launch {{package_name}} bringup.launch.py
```

另一个终端加载相同环境后：

```bash
ros2 topic echo /demo_robot/chatter --once
```

`talker` 发布 `std_msgs/msg/String`，`listener` 订阅同一命名空间下的 `chatter`。
`config/robot.yaml` 定义机器人标识和 `use_sim_time`，Launch 支持
`namespace:=robot_a` 与 `params_file:=/absolute/robot.yaml`。
此模板不启动仿真时钟或 TF；使用真实时钟，故默认 `use_sim_time: false`。

```bash
colcon test --packages-select {{package_name}} --event-handlers console_direct+
colcon test-result --verbose
```

测试检查安装的 Launch 可加载、节点数量和参数文件。可把 Launch 中的 demo 节点替换为实际机器人节点。
