"""命令执行前检查操作系统和当前终端的 ROS 环境。"""

import os
import platform
import shutil


class EnvironmentCheckError(RuntimeError):
    """ROS 环境不符合模板要求，由调用方决定如何显示。"""


def environment_status() -> dict:
    """返回环境事实，供命令行检查与终端界面共同使用。"""
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}

    system_ok = (
        release.get("ID") == "ubuntu" and release.get("VERSION_ID") == "24.04"
    )
    distro = os.environ.get("ROS_DISTRO", "")
    ros_version = os.environ.get("ROS_VERSION", "")
    ros_command = shutil.which("ros2")
    system = release.get("PRETTY_NAME") or (
        f"{release.get('ID', '未知系统')} {release.get('VERSION_ID', '未知版本')}"
    )
    return {
        "release": release, "system": system, "system_ok": system_ok,
        "distro": distro, "ros_version": ros_version, "ros_command": ros_command,
        "ready": bool(system_ok and distro == "jazzy" and ros_version == "2" and ros_command),
    }


def check_environment() -> None:
    """ROS 创建环境不满足要求时显示检测结果并退出。"""
    status = environment_status()
    if status["ready"]:
        return
    release, system, system_ok = status["release"], status["system"], status["system_ok"]
    distro, ros_version, ros_command = status["distro"], status["ros_version"], status["ros_command"]
    lines = [
        "当前环境不符合运行要求，命令已停止。",
        "需要环境：Ubuntu 24.04 + ROS 2 Jazzy（已加载到当前终端）",
        f"当前系统：{system}",
        f"当前系统标识：{release.get('ID', '未知')} / {release.get('VERSION_ID', '未知')}",
        f"当前 ROS_DISTRO：{distro or '未设置'}",
        f"当前 ROS_VERSION：{ros_version or '未设置'}",
        f"当前 ros2 命令：{ros_command or '未找到'}",
    ]
    if not system_ok:
        lines.append("建议：在 Ubuntu 24.04 主机或容器中运行。")
    if distro != "jazzy" or ros_version != "2" or not ros_command:
        lines.append("建议：安装 ROS 2 Jazzy，并在当前终端执行：\n"
                     "  source /opt/ros/jazzy/setup.bash\n自定义安装请加载对应的 Jazzy setup.bash。")
    raise EnvironmentCheckError("\n".join(lines))
