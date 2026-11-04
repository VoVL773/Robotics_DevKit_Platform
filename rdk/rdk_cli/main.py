"""rdk robot-cli 的命令行入口。

命令结构：
    robot-cli template list          列出所有模板
    robot-cli template info NAME     查看某个模板的详细信息
    robot-cli project create NAME    按模板创建一个项目
"""

import re
import shlex
import subprocess
from importlib.resources import files
from pathlib import Path

import typer

from rdk_cli.registry import TEMPLATES  # 从 registry.py 中取出我们写好的模板登记表。
from rdk_cli.environment import check_environment

# 模板作为包资源发布，源码安装和 wheel 安装使用同一定位方式。
TEMPLATE_DIR = files("rdk_templates")

# ROS 2 包名规则：小写字母开头，只含小写字母、数字、下划线，且不能以下划线结尾。
PACKAGE_NAME_RE = re.compile(r"[a-z](?:[a-z0-9_]*[a-z0-9])?")

# 模板中用来占位包名的地方，复制文件时会替换成真实的包名。
PLACEHOLDER = "{{package_name}}"

# 命令组
app = typer.Typer(help="rdk 机器人开发工具链：查看模板、创建 ROS 2 与 PyTorch 项目。")
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
            f"{info['description']} [{info['status']}]"
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
    typer.echo(f"模板类型：{info['kind']}")
    typer.echo(f"可用状态：{info['status']}")
    typer.echo(f"维护者：{info['maintainer']}")
    typer.echo(f"环境要求：{info['environment']}")
    typer.echo("创建参数：--name（必填）、--output、--license（仅 ROS 包）")


def _apply_template_overlay(template: str, project_path: Path, package: str) -> None:
    """把 templates/<template>/ 下的文件复制进生成的项目。

    目录名和文件内容中的 {{package_name}} 都会替换成真实包名，
    这样模板本身不必绑定某个具体的包。
    """

    overlay = TEMPLATE_DIR / template
    if not overlay.is_dir():
        _fail(f"模板资源缺失：{template}，请重新安装 robot-cli")

    for src in sorted(overlay.rglob("*")):
        if "__pycache__" in src.parts or src.suffix == ".pyc":
            continue
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
    name: str = typer.Option(..., "--name", help="新项目名称"),
    output: str = typer.Option(".", "--output", help="项目生成位置"),
    license: str = typer.Option(
        "Apache-2.0",
        "--license",
        help="开源许可证，例如 Apache-2.0、MIT",
    ),
) -> None:
    """按类型生成 ROS 2 软件包或独立的 PyTorch 训练项目。"""

    # 1. 模板必须存在
    if template not in TEMPLATES:
        _fail(
            f"找不到模板 '{template}'，"
            "请使用 robot-cli template list 查看可用模板"
        )

    info = TEMPLATES[template]

    if info["status"] != "available":
        _fail(f"模板 '{template}' 尚不可用")
    if not (TEMPLATE_DIR / template).is_dir():
        _fail(f"模板资源缺失：{template}，请重新安装 robot-cli")

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

    if info["kind"] == "pytorch":
        try:
            project_path.mkdir(parents=True, exist_ok=False)
            _apply_template_overlay(template, project_path, name)
        except OSError as exc:
            _fail(f"创建训练项目失败：{exc}")
        typer.secho(f"\n项目创建成功：{project_path}", fg=typer.colors.GREEN)
        typer.echo("\n下一步：")
        typer.echo(f"  cd {shlex.quote(str(project_path))}")
        typer.echo("  python3 -m venv .venv")
        typer.echo("  source .venv/bin/activate")
        typer.echo("  python -m pip install -e '.[dev]'")
        typer.echo("  python -m training.train --config configs/default.json")
        typer.echo("  python -m training.evaluate --checkpoint outputs/checkpoint.pt")
        return

    check_environment()
    output_path.mkdir(parents=True, exist_ok=True)
    cpp = info["kind"] == "ros2_cpp"
    command = [
        "ros2", "pkg", "create", name,
        "--build-type", "ament_cmake" if cpp else "ament_python",
        "--license", license,
        "--dependencies", "rclcpp" if cpp else "rclpy",
        "--node-name", "hello_node",
        "--destination-directory", str(output_path),
    ]
    try:
        subprocess.run(command, check=True)
        _apply_template_overlay(template, project_path, name)
    except FileNotFoundError:
        _fail("找不到 ros2 命令，请先执行 source /opt/ros/jazzy/setup.bash")
    except subprocess.CalledProcessError as exc:
        _fail(f"ROS 2 创建软件包失败，退出码：{exc.returncode}")
    except OSError as exc:
        _fail(f"写入项目失败：{exc}")

    workspace = output_path.parent if output_path.name == "src" else output_path
    typer.secho(f"\n项目创建成功：{project_path}", fg=typer.colors.GREEN)
    typer.echo("\n下一步：")
    typer.echo(f"  cd {shlex.quote(str(workspace))}")
    typer.echo("  colcon build --symlink-install")
    typer.echo("  source install/setup.bash")
    typer.echo(f"  ros2 run {name} hello_node")
    typer.echo(f"  ros2 launch {name} hello.launch.py")


if __name__ == "__main__":
    app()
