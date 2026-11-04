"""内置模板元数据；生成逻辑按 kind 分派，而非开发语言。"""

TEMPLATES = {
    "ros2-python": {
        "kind": "ros2_python",
        "status": "available",
        "maintainer": "Robotics DevKit Platform contributors",
        "environment": "Ubuntu 24.04 + ROS 2 Jazzy + colcon",
        "version": "1.0.0",  
        "description": "ROS 2 Python 软件包模板",
        "ros_distro": ["jazzy"],
        "language": "Python",
    },
    "ros2-cpp": {
        "kind": "ros2_cpp",
        "status": "available",
        "maintainer": "Robotics DevKit Platform contributors",
        "environment": "Ubuntu 24.04 + ROS 2 Jazzy + colcon + C++17 编译器",
        "version": "1.0.0",
        "description": "ROS 2 C++ 软件包模板",
        "ros_distro": ["jazzy"],
        "language": "C++",
    },
    "pytorch-training": {
        "kind": "pytorch",
        "status": "available",
        "maintainer": "Robotics DevKit Platform contributors",
        "environment": "Python >= 3.10 + PyTorch >= 2.2（CPU 即可，无需 ROS）",
        "version": "1.0.0",
        "description": "PyTorch 模型训练模板",
        "ros_distro": [],
        "language": "Python",
    },
}
