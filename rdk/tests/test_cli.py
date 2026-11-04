"""robot-cli 的基础测试：只验证纯逻辑，不需要 ROS 2 环境。"""

from typer.testing import CliRunner
import pytest

from rdk_cli.main import app
from rdk_cli import environment

runner = CliRunner()


@pytest.fixture(autouse=True)
def supported_environment(monkeypatch):
    """测试不依赖执行机器是否安装 ROS。"""
    monkeypatch.setattr(environment.platform, "freedesktop_os_release", lambda: {
        "ID": "ubuntu", "VERSION_ID": "24.04", "PRETTY_NAME": "Ubuntu 24.04 LTS",
    })
    monkeypatch.setenv("ROS_DISTRO", "jazzy")
    monkeypatch.setenv("ROS_VERSION", "2")
    monkeypatch.setattr(environment.shutil, "which", lambda name: "/opt/ros/jazzy/bin/ros2")


def test_template_list_contains_ros2_python() -> None:
    result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 0
    assert "ros2-python" in result.output


def test_template_info_unknown_template() -> None:
    result = runner.invoke(app, ["template", "info", "no-such-template"])
    assert result.exit_code == 1
    assert "找不到模板" in result.output


def test_project_create_rejects_invalid_name() -> None:
    result = runner.invoke(
        app,
        ["project", "create", "ros2-python", "--name", "Bad-Name"],
    )
    assert result.exit_code == 1
    assert "小写字母" in result.output


@pytest.mark.parametrize("release", [
    {"ID": "ubuntu", "VERSION_ID": "22.04", "PRETTY_NAME": "Ubuntu 22.04 LTS"},
    {"ID": "debian", "VERSION_ID": "24.04", "PRETTY_NAME": "Debian"},
])
def test_rejects_wrong_os(monkeypatch, release):
    monkeypatch.setattr(environment.platform, "freedesktop_os_release", lambda: release)
    result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 1
    assert release["PRETTY_NAME"] in result.output
    assert "需要环境：Ubuntu 24.04 + ROS 2 Jazzy" in result.output
    assert "ros2-python" not in result.output


@pytest.mark.parametrize("variable,value", [
    ("ROS_DISTRO", "humble"), ("ROS_DISTRO", ""), ("ROS_VERSION", "1"),
])
def test_rejects_wrong_or_unloaded_ros(monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 1
    assert f"当前 {variable}：{value or '未设置'}" in result.output
    assert "source /opt/ros/jazzy/setup.bash" in result.output


def test_missing_ros_command_prevents_creation(monkeypatch, tmp_path):
    monkeypatch.setattr(environment.shutil, "which", lambda name: None)
    output = tmp_path / "not_created"
    result = runner.invoke(app, [
        "project", "create", "ros2-python", "--name", "demo", "--output", str(output),
    ])
    assert result.exit_code == 1
    assert "当前 ros2 命令：未找到" in result.output
    assert not output.exists()


def test_unreadable_os_release(monkeypatch):
    def unavailable():
        raise OSError("os-release unavailable")
    monkeypatch.setattr(environment.platform, "freedesktop_os_release", unavailable)
    result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 1
    assert "未知系统" in result.output


def test_top_level_help_available_in_unsupported_environment(monkeypatch):
    monkeypatch.setenv("ROS_DISTRO", "humble")
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "template" in result.output
