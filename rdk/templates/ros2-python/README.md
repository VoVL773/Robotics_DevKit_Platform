# {{package_name}}

由 `robot-cli project create ros2-python --name {{package_name}}` 生成的 ROS 2 Python 软件包。

## 目录结构

```
{{package_name}}/
├── package.xml              # 软件包元信息（名称、依赖、许可证）
├── setup.py                 # Python 打包配置，console_scripts 里登记可执行文件
├── setup.cfg                # ament_python 安装路径配置
├── resource/{{package_name}}  # ament 资源索引标记文件（空文件，不要删）
├── {{package_name}}/
│   ├── __init__.py
│   └── hello_node.py        # 示例节点：每秒打印一条日志
└── test/                    # ROS 2 自带的代码风格测试
```

## 编译并运行

在 ROS 2 工作空间根目录（例如 `~/demo_ws`，里面有 `src/{{package_name}}`）执行：

```bash
# 1. 编译（--symlink-install 让 Python 文件修改后无需重新编译）
colcon build --symlink-install

# 2. 让当前终端找到刚编译出来的包
source install/setup.bash

# 3. 运行示例节点
ros2 run {{package_name}} hello_node
```

看到下面的输出就说明成功了：

```text
[INFO] [1750000000.123456789] [hello_node]: hello_node 已启动，按 Ctrl+C 退出
[INFO] [1750000000.623456789] [hello_node]: hello from {{package_name}} #1
[INFO] [1750000001.123456789] [hello_node]: hello from {{package_name}} #2
```

## 修改示例

编辑 `{{package_name}}/hello_node.py` 的 `_on_timer` 方法即可改掉打印内容。
想换节点名，就同时修改 `setup.py` 里 `console_scripts` 的名字。
