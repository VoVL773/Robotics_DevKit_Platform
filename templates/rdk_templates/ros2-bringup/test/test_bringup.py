"""导入并实例化 Launch，检查安装的配置和节点配置数量。"""
import importlib.util
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
import yaml


def test_bringup():
    share = Path(get_package_share_directory('{{package_name}}'))
    config = yaml.safe_load((share / 'config/robot.yaml').read_text())
    assert config['/**']['ros__parameters']['use_sim_time'] is False
    spec = importlib.util.spec_from_file_location('bringup', share / 'launch/bringup.launch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    description = module.generate_launch_description()
    assert len([item for item in description.entities if isinstance(item, Node)]) == 2
