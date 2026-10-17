"""
Example node for {{package_name}}: logs a message once per second.

这是 rdk 模板提供的最简 ROS 2 节点：
- 用继承 Node 的类组织代码；
- 用 create_timer 让回调每秒执行一次；
- 用 get_logger().info() 输出日志。

运行方式（在 ROS 2 工作空间根目录下）：
    colcon build --symlink-install
    source install/setup.bash
    ros2 run {{package_name}} hello_node
"""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class HelloNode(Node):
    """Minimal ROS 2 node that logs a hello message every second."""

    def __init__(self) -> None:
        super().__init__('hello_node')
        self._count = 0
        # 每 1.0 秒调用一次 _on_timer
        self._timer = self.create_timer(1.0, self._on_timer)
        self.get_logger().info('hello_node 已启动，按 Ctrl+C 退出')

    def _on_timer(self) -> None:
        self._count += 1
        self.get_logger().info(f'hello from {{package_name}} #{self._count}')


def main(args: list[str] | None = None) -> None:
    """Start the node and spin until Ctrl+C."""
    rclpy.init(args=args)
    node = HelloNode()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        # 收到 Ctrl+C / SIGTERM 时 rclpy 已经关掉 context，安静退出即可
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
