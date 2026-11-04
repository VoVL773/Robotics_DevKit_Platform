"""命令执行前检查操作系统和当前终端的 ROS 环境。"""

import os
import platform
import shutil

import typer


def check_environment() -> None:
    """不满足要求时显示检测结果并退出，不执行后续业务操作。"""
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
    if system_ok and distro == "jazzy" and ros_version == "2" and ros_command:
        return

    system = release.get("PRETTY_NAME") or (
        f"{release.get('ID', '未知系统')} {release.get('VERSION_ID', '未知版本')}"
    )
    typer.secho("错误：当前环境不符合运行要求，命令已停止。", fg=typer.colors.RED, err=True)
    typer.echo("需要环境：Ubuntu 24.04 + ROS 2 Jazzy（已加载到当前终端）", err=True)
    typer.echo(f"当前系统：{system}", err=True)
    typer.echo(f"当前系统标识：{release.get('ID', '未知')} / {release.get('VERSION_ID', '未知')}", err=True)
    typer.echo(f"当前 ROS_DISTRO：{distro or '未设置'}", err=True)
    typer.echo(f"当前 ROS_VERSION：{ros_version or '未设置'}", err=True)
    typer.echo(f"当前 ros2 命令：{ros_command or '未找到'}", err=True)
    if not system_ok:
        typer.echo("建议：在 Ubuntu 24.04 主机或容器中运行。", err=True)
    if distro != "jazzy" or ros_version != "2" or not ros_command:
        typer.echo(
            "建议：安装 ROS 2 Jazzy，并在当前终端执行：\n"
            "  source /opt/ros/jazzy/setup.bash\n"
            "自定义安装请加载对应的 Jazzy setup.bash。",
            err=True,
        )
    raise typer.Exit(code=1)
