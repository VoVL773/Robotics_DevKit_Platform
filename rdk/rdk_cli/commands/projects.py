"""项目创建命令：将 Typer 参数转换为请求，再展示服务返回的结果。"""
import subprocess
import xml.etree.ElementTree as ET
from typing import Annotated, Optional
from pathlib import Path
import sys

import typer
from rdk_cli.cli_locale import ChineseTyper

from rdk_cli import template_store as store
from rdk_cli import terminal as ui
from rdk_cli.commands.common import fail
from rdk_cli.environment import EnvironmentCheckError, check_environment
from rdk_cli.environments.profiles import EnvironmentError
from rdk_cli.environments.projects import create_in_container, create_in_existing
from rdk_cli.environments.discovery import discover
from rdk_cli.environments.profiles import get_profile
from rdk_cli.project_service import ProjectRequest, create_project, prepare_project, run_smoke_tests

app = ChineseTyper(help='从固定版本模板创建独立项目。', no_args_is_help=True)


@app.command('create')
def project_create(
    template: str = typer.Argument(..., help='模板名或 name@version，例如 ros2-cpp-package@1.0.0'),
    name: str = typer.Option(..., '--name', help='项目/软件包名称'),
    output: str = typer.Option('.', '--output'),
    node_name: Optional[str] = typer.Option(None, '--node-name'),
    maintainer: Optional[str] = typer.Option(None, '--maintainer'),
    maintainer_email: Optional[str] = typer.Option(None, '--maintainer-email'),
    license: Optional[str] = typer.Option(None, '--license'),
    ros_distro: Optional[str] = typer.Option(None, '--ros-distro'),
    param: Optional[list[str]] = typer.Option(None, '--param', help='可重复的模板参数 KEY=VALUE'),
    examples: Annotated[bool, typer.Option('--examples/--no-examples', help='生成示例代码 / 仅生成工程骨架')] = True,
    git: bool = typer.Option(False, '--git', help='初始化 Git 仓库，不自动提交'),
    ci: bool = typer.Option(False, '--ci', help='生成 GitHub Actions 冒烟测试'),
    smoke_test: bool = typer.Option(False, '--smoke-test', help='创建后构建/测试，依赖须预先安装'),
    container: bool = typer.Option(False, '--container', help='在匹配发行版的容器中创建/构建'),
    container_name: Optional[str] = typer.Option(None, '--container-name', help='开发容器名'),
    mount: Optional[str] = typer.Option(None, '--mount', help='挂载到 /workspace 的宿主机目录，须包含输出位置'),
    env_root: str = typer.Option('.robot-cli/environments', '--env-root', help='环境锁和构建上下文目录'),
    host_only: bool = typer.Option(False, '--host-only', help='只用当前环境，不提示创建容器'),
    reuse_container: Optional[str] = typer.Option(None, '--reuse-container', help='复用已有容器，保留其挂载配置'),
):
    """校验参数并生成独立项目，记录模板版本。"""
    try:
        supplied = {
            key: value for key, value in [
                ('node_name', node_name), ('maintainer', maintainer),
                ('maintainer_email', maintainer_email), ('license', license), ('ros_distro', ros_distro),
            ] if value is not None
        }
        request = ProjectRequest.from_cli(template, name, output, supplied, param or [],
                                          initialize_git=git, ci=ci, smoke_test=smoke_test, include_examples=examples)
        plan = prepare_project(request, check_host=False)
        use_container = container or container_name is not None or mount is not None or reuse_container is not None
        if reuse_container and (container_name or mount):
            raise EnvironmentError('--reuse-container 不能与 --container-name/--mount 同时使用；已有容器使用其既有挂载')
        if host_only and use_container:
            raise EnvironmentError('--host-only 不能与容器参数同时使用')
        if plan.kind.startswith('ros2_'):
            if not use_container:
                try:
                    check_environment(plan.values.get('ros_distro', plan.record['ros_distro'][0]))
                except EnvironmentCheckError as error:
                    if host_only or not sys.stdin.isatty():
                        raise EnvironmentCheckError(str(error) +
                            '\n可使用 --container --container-name <容器名> --mount <宿主机目录> 自动准备匹配环境。') from error
                    typer.echo(str(error))
                    if not typer.confirm('检测到环境差异，是否使用匹配发行版的开发容器？', default=True):
                        raise typer.Exit(1)
                    use_container = True
            if use_container:
                ros = plan.values['ros_distro']
                if not reuse_container and not container_name and sys.stdin.isatty():
                    candidates = [c for c in discover(get_profile(f'ros2-{ros}-dev')) if c.compatible]
                    for index, candidate in enumerate(candidates, 1):
                        mapped = candidate.mapped_path(plan.output_path)
                        typer.echo(f"{index}. {candidate.name}（{'运行中' if candidate.running else '已停止，选择后启动'}）"
                                   f" 输出映射：{mapped or '未覆盖当前输出目录'}")
                        for binding in candidate.mounts:
                            if binding['type'] == 'bind':
                                typer.echo(f"   {binding['source']} → {binding['target']}")
                    if candidates:
                        choice = typer.prompt('选择已有容器编号（0 新建；无输出映射时请先调整输出目录）', default=next((i for i, c in enumerate(candidates, 1) if c.mapped_path(plan.output_path)), 0), type=int)
                        if not 0 <= choice <= len(candidates):
                            raise EnvironmentError('容器编号超出范围')
                        if choice:
                            reuse_container = candidates[choice - 1].name
                if reuse_container:
                    runtime = create_in_existing(plan, reuse_container)
                    ui.success(plan.project_path, plan.reference)
                    typer.echo(f"已复用容器：{runtime['container']}；容器内输出：{runtime['output']}；系统依赖未修改，CLI 安装在 /tmp 隔离目录。")
                    return
                if not container_name:
                    default_name = f'rdk-{ros}-{name}'
                    container_name = typer.prompt('容器名称', default=default_name) if sys.stdin.isatty() else default_name
                if not mount:
                    mount = typer.prompt('宿主机挂载目录（容器内 /workspace）', default=str(plan.output_path)) if sys.stdin.isatty() else str(plan.output_path)
                runtime = create_in_container(plan, container_name, mount, Path(env_root))
                ui.success(plan.project_path, plan.reference)
                typer.echo(f"开发容器：{runtime['container']}；挂载目录：{Path(mount).expanduser().resolve()} → /workspace")
                typer.echo(f"进入容器：docker exec -it {runtime['container']} bash")
                return
        elif use_container:
            raise EnvironmentError('项目创建的自动容器路由目前面向 ROS 模板；PyTorch 可先用 env shell 进入开发环境')
        create_project(plan)
        ui.success(plan.project_path, plan.reference)
        ui.notice('下一步', 'bold cyan')
        for command in plan.next_steps():
            typer.echo('  ' + command)
        if request.smoke_test:
            run_smoke_tests(plan)
            ui.notice('✓ 冒烟测试通过。', 'bold green')
    except (store.TemplateError, EnvironmentCheckError, EnvironmentError, OSError, ET.ParseError) as error:
        fail(str(error))
    except subprocess.CalledProcessError as error:
        fail(f'外部命令失败，退出码 {error.returncode}。已生成文件保留，请检查日志和依赖后重试。')
