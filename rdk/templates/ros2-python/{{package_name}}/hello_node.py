"""定时输出日志，演示 ROS 2 参数与节点生命周期。"""

import math

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class HelloNode(Node):
    """使用 message 和 period 参数配置启动行为。"""

    def __init__(self):
        super().__init__('{{node_name}}')
        self.declare_parameter('message', 'hello from {{package_name}}')
        self.declare_parameter('period', 1.0)
        period = self.get_parameter('period').value
        if not math.isfinite(period) or period <= 0:
            self.destroy_node()
            raise ValueError('period must be finite and greater than zero')
        self._count = 0
        self._timer = self.create_timer(period, self._on_timer)
        self.get_logger().info('{{node_name}} 已启动，按 Ctrl+C 退出')

    def _on_timer(self):
        self._count += 1
        message = self.get_parameter('message').value
        self.get_logger().info(f'{message} #{self._count}')


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = HelloNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
