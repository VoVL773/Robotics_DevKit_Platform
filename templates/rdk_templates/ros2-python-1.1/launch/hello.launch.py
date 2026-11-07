"""启动示例节点并加载安装目录中的参数文件。"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory('{{package_name}}')) / 'config' / 'hello.yaml'
    return LaunchDescription([
        Node(package='{{package_name}}', executable='{{node_name}}',
             name='{{node_name}}', parameters=[str(config)], output='screen'),
    ])
