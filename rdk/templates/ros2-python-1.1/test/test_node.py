"""验证实际 rclpy 节点、参数和计时器。"""
from time import monotonic

import pytest
import rclpy
from rclpy.parameter import Parameter
from {{package_name}}.hello_node import HelloNode


def test_timer():
    rclpy.init(args=['--ros-args', '-p', 'period:=0.01'])
    node = HelloNode()
    try:
        deadline = monotonic() + 3
        while node._count == 0 and monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        assert node._count > 0
        assert node.get_parameter('message').value == 'hello from {{package_name}}'
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_invalid_period():
    rclpy.init(args=['--ros-args', '-p', 'period:=0.0'])
    try:
        with pytest.raises(ValueError, match='period'):
            HelloNode()
    finally:
        rclpy.shutdown()
