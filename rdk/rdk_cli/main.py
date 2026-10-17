"""rdk robot-cli 的命令行入口。

命令结构：
    robot-cli template list          列出所有模板
    robot-cli template info NAME     查看某个模板的详细信息
    robot-cli project create NAME    按模板创建一个 ROS 2 软件包
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import typer

from rdk_cli.registry import TEMPLATES  # 从 registry.py 中取出我们写好的模板登记表。

# 模板目录在仓库根目录下（rdk/templates），main.py 位于 rdk/rdk_cli/main.py。
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# ROS 2 包名规则：小写字母开头，只含小写字母、数字、下划线，且不能以下划线结尾。
PACKAGE_NAME_RE = re.compile(r"[a-z](?:[a-z0-9_]*[a-z0-9])?")

# 模板中用来占位包名的地方，复制文件时会替换成真实的包名。
PLACEHOLDER = "{{package_name}}"

# 命令组
app = typer.Typer(help="rdk 机器人开发工具链：查看模板、创建 ROS 2 项目。")
template_app = typer.Typer(help="查看内置模板。", no_args_is_help=True)
project_app = typer.Typer(help="创建新项目。", no_args_is_help=True)

# template_app / project_app 注册到主命令
app.add_typer(template_app, name="template")
app.add_typer(project_app, name="project")


def _fail(message: str) -> None:
    """打印错误信息并以退出码 1 结束。"""
    typer.secho(f"错误：{message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


@template_app.command("list")
def template_list() -> None:
    """列出所有可用模板。"""

    typer.echo(f"{'名称':20} {'版本':10} 说明")
    typer.echo("-" * 60)

    for name, info in TEMPLATES.items():
        typer.echo(
            f"{name:20} "
            f"{info['version']:10} "
            f"{info['description']}"
        )


@template_app.command("info")
def template_info(name: str) -> None:
    """查看指定模板的详细信息。"""

    if name not in TEMPLATES:
        _fail(
            f"找不到模板 '{name}'，"
            "请使用 robot-cli template list 查看可用模板"
        )

    info = TEMPLATES[name]
    ros_distro = ", ".join(info["ros_distro"]) or "不适用"

    typer.echo(f"模板名称：{name}")
    typer.echo(f"模板版本：{info['version']}")
    typer.echo(f"模板说明：{info['description']}")
    typer.echo(f"兼容 ROS 2：{ros_distro}")
    typer.echo(f"开发语言：{info['language']}")


def _apply_template_overlay(template: str, project_path: Path, package: str) -> None:
    """把 templates/<template>/ 下的文件复制进生成的项目。

    目录名和文件内容中的 {{package_name}} 都会替换成真实包名，
    这样模板本身不必绑定某个具体的包。
    """

    overlay = TEMPLATE_DIR / template
    if not overlay.is_dir():
        return

    for src in sorted(overlay.rglob("*")):
        relative = str(src.relative_to(overlay)).replace(PLACEHOLDER, package)
        dst = project_path / relative

        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")
        dst.write_text(text.replace(PLACEHOLDER, package), encoding="utf-8")


@project_app.command("create")
def project_create(
    template: str = typer.Argument(..., help="模板名称，例如 ros2-python"),
    name: str = typer.Option(..., "--name", help="新项目（ROS 2 软件包）名称"),
    output: str = typer.Option(".", "--output", help="项目生成位置"),
    license: str = typer.Option(
        "Apache-2.0",
        "--license",
        help="开源许可证，例如 Apache-2.0、MIT",
    ),
) -> None:
    """按模板创建一个新的 ROS 2 软件包。"""

    # 1. 模板必须存在
    if template not in TEMPLATES:
        _fail(
            f"找不到模板 '{template}'，"
            "请使用 robot-cli template list 查看可用模板"
        )

    info = TEMPLATES[template]

    # 2. 目前只实现了 Python 模板
    if info["language"] != "Python":
        _fail(f"模板 '{template}' 尚未实现（只支持 Python 模板）")

    # 3. 包名必须是合法的 ROS 2 包名
    if not PACKAGE_NAME_RE.fullmatch(name):
        _fail(
            "项目名必须以小写字母开头，"
            "只能包含小写字母、数字和下划线，且不能以下划线结尾"
        )

    # 4. 展开 ~，并转换成绝对路径
    output_path = Path(output).expanduser().resolve()
    project_path = output_path / name

    # 5. 检查目标目录是否已经存在
    if project_path.exists():
        _fail(f"目标路径已经存在：{project_path}")

    # 6. 检查 ros2 命令；没有加载环境时给出明确提示
    if shutil.which("ros2") is None:
        _fail("找不到 ros2 命令，请先执行 source /opt/ros/jazzy/setup.bash")

    ros_distro = os.environ.get("ROS_DISTRO")
    if ros_distro is None:
        typer.secho(
            "警告：环境变量 ROS_DISTRO 未设置，可能还没有 source ROS 2 环境",
            fg=typer.colors.YELLOW,
            err=True,
        )
    elif ros_distro not in info["ros_distro"]:
        _fail(
            f"模板 '{template}' 只兼容 ROS 2 {', '.join(info['ros_distro'])}，"
            f"当前是 {ros_distro}"
        )

    # 7. 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)

    # 8. 用 ros2 pkg create 生成软件包骨架
    command = [
        "ros2",
        "pkg",
        "create",
        name,
        "--build-type",
        "ament_python",
        "--license",
        license,
        "--dependencies",
        "rclpy",
        "--node-name",
        "hello_node",
        "--destination-directory",
        str(output_path),
    ]

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        _fail("找不到 ros2 命令，请先执行 source /opt/ros/jazzy/setup.bash")
    except subprocess.CalledProcessError as exc:
        _fail(f"ROS 2 创建软件包失败，退出码：{exc.returncode}")

    # 9. 用模板内容覆盖/补充生成的骨架（例如一个能跑的示例节点）
    _apply_template_overlay(template, project_path, name)

    # 10. 告诉用户下一步怎么做
    # 如果项目生成在 src/ 下，colcon 应该在工作空间根目录（src 的上一级）执行，
    # 否则 build/install 会堆在 src/ 里。
    workspace = output_path.parent if output_path.name == "src" else output_path

    typer.secho(f"\n项目创建成功：{project_path}", fg=typer.colors.GREEN)
    typer.echo("\n下一步：")
    typer.echo(f"  cd {workspace}")
    typer.echo("  colcon build --symlink-install")
    typer.echo("  source install/setup.bash")
    typer.echo(f"  ros2 run {name} hello_node")


if __name__ == "__main__":
    app()
