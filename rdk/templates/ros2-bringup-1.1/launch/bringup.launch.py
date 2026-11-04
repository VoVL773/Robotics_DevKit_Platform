"""启动两个独立的 ROS demo 节点，机器人配置通过 Launch 参数选择。"""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory('{{package_name}}')) / 'config' / 'robot.yaml'
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value='demo_robot'),
        DeclareLaunchArgument('params_file', default_value=str(config)),
        Node(package='demo_nodes_cpp', executable='talker', name='talker',
             namespace=LaunchConfiguration('namespace'),
             parameters=[LaunchConfiguration('params_file')], output='screen'),
        Node(package='demo_nodes_cpp', executable='listener', name='listener',
             namespace=LaunchConfiguration('namespace'),
             parameters=[LaunchConfiguration('params_file')], output='screen'),
    ])
