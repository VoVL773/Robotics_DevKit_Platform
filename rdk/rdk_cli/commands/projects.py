"""项目创建命令：将 Typer 参数转换为请求，再展示服务返回的结果。"""
import subprocess
import xml.etree.ElementTree as ET
from typing import Optional

import typer

from rdk_cli import template_store as store
from rdk_cli import terminal as ui
from rdk_cli.commands.common import fail
from rdk_cli.environment import EnvironmentCheckError
from rdk_cli.project_service import ProjectRequest, create_project, prepare_project, run_smoke_tests

app = typer.Typer(help='从固定版本模板创建独立项目。', no_args_is_help=True)


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
    git: bool = typer.Option(False, '--git', help='初始化 Git 仓库，不自动提交'),
    ci: bool = typer.Option(False, '--ci', help='生成 GitHub Actions 冒烟测试'),
    smoke_test: bool = typer.Option(False, '--smoke-test', help='创建后构建/测试，依赖须预先安装'),
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
                                          initialize_git=git, ci=ci, smoke_test=smoke_test)
        plan = prepare_project(request)
        create_project(plan)
        ui.success(plan.project_path, plan.reference)
        ui.notice('下一步', 'bold cyan')
        for command in plan.next_steps():
            typer.echo('  ' + command)
        if request.smoke_test:
            run_smoke_tests(plan)
            ui.notice('✓ 冒烟测试通过。', 'bold green')
    except (store.TemplateError, EnvironmentCheckError, OSError, ET.ParseError) as error:
        fail(str(error))
    except subprocess.CalledProcessError as error:
        fail(f'外部命令失败，退出码 {error.returncode}。已生成文件保留，请检查日志和依赖后重试。')
