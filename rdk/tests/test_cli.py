"""robot-cli 的基础测试：只验证纯逻辑，不需要 ROS 2 环境。"""

from typer.testing import CliRunner

from rdk_cli.main import app

runner = CliRunner()


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
