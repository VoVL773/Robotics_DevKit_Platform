"""开发环境命令适配器：中文报告、JSON 输出与可复现构建。"""
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rdk_cli.commands.common import fail
from rdk_cli.environments import containers
from rdk_cli.environments.context import configure, write_json
from rdk_cli.environments.doctor import diagnose
from rdk_cli.environments.profiles import EnvironmentError, PROFILES, get_profile

app = typer.Typer(help='开发环境兼容检查、锁定配置与容器生命周期。', no_args_is_help=True)
console = Console()
DEFAULT_ROOT = Path('.robot-cli/environments')


def show_result(result):
    for key, value in result.items():
        typer.echo(f'{key}: {value}')


@app.command('list')
def list_environments(as_json: bool = typer.Option(False, '--json')):
    """列出版本化 CPU/GPU 环境及兼容范围，不需要 Docker。"""
    if as_json:
        typer.echo(json.dumps([p.data() for p in PROFILES.values()], ensure_ascii=False, indent=2))
        return
    table = Table(title='开发环境兼容矩阵 · v1.0.0')
    for label in ('环境', 'Ubuntu', 'ROS', 'Python', 'CUDA / 最低驱动', '镜像版本'):
        table.add_column(label)
    for p in PROFILES.values():
        table.add_row(p.name, p.ubuntu, p.ros, p.python,
                      f'{p.cuda} / {p.driver_min}' if p.gpu else 'CPU / 无需 GPU', p.version)
    console.print(table)
    typer.echo('配置定义不等于已经验证；env verify 成功后记录本机验收。hamble 名称兼容映射为 humble。')


@app.command('doctor')
def doctor(
    profile: str = typer.Argument('ros2-jazzy-dev'),
    as_json: bool = typer.Option(False, '--json'),
    output: Path | None = typer.Option(None, '--output', help='保存 JSON 报告'),
    template: str | None = typer.Option(None, '--template', help='同时核对模板兼容声明'),
):
    """只读诊断；宿主机或容器路线可用时成功，否则退出码 1。"""
    try:
        from rdk_cli import template_store
        record = template_store.resolve(template) if template else None
        report = diagnose(get_profile(profile), Path.cwd(), record)
        if output:
            write_json(output, report.data())
        if as_json:
            typer.echo(json.dumps(report.data(), ensure_ascii=False, indent=2))
        else:
            table = Table(title=f'环境兼容性诊断 · {report.profile.name}')
            for label in ('检查', '结果', '事实 / 修复建议'):
                table.add_column(label)
            for check in report.checks:
                style = {'pass': 'green', 'warn': 'yellow', 'fail': 'red'}[check.status]
                table.add_row(check.name, f'[{style}]{check.status}[/{style}]',
                              check.detail + ('\n建议：' + check.fix if check.fix else ''))
            console.print(table)
            typer.echo(f'宿主机开发：{"可用" if report.host_ready else "不符合"}；'
                       f'容器运行条件：{"可用（还需构建/验证镜像）" if report.container_ready else "不符合"}')
        if not report.host_ready and not report.container_ready:
            raise typer.Exit(1)
    except (EnvironmentError, OSError, ValueError) as error:
        fail(str(error))


@app.command('configure')
def configure_environment(
    profile: str, root: Path = typer.Option(DEFAULT_ROOT, '--root'),
    update_lock: bool = typer.Option(False, '--update-lock'),
    with_torch: bool = typer.Option(False, '--with-torch'),
):
    """解析并锁定镜像/APT，导出 Dockerfile、依赖锁、Dev Container（需要 Docker 和网络）。"""
    try:
        p = get_profile(profile)
        containers.require_docker()
        context = containers.context_path(p, root)
        lock = configure(p, context, update_lock, with_torch or p.gpu)
        show_result({'context': context, 'base_digest': lock['base_digest'],
                     'devcontainer': context / '.devcontainer/devcontainer.json'})
    except (EnvironmentError, OSError, ValueError) as error:
        fail(str(error))


@app.command('build')
def build_environment(
    profile: str, root: Path = typer.Option(DEFAULT_ROOT, '--root'),
    container: bool = typer.Option(False, '--container', help='即使宿主机合格也构建镜像'),
    update_lock: bool = typer.Option(False, '--update-lock', help='显式更新锁并记录历史'),
    with_torch: bool = typer.Option(False, '--with-torch', help='安装锁定 CPU PyTorch；GPU 环境默认安装'),
):
    """宿主机合格时跳过，否则按锁构建；不会自动安装宿主机驱动。"""
    try:
        p = get_profile(profile)
        show_result(containers.build(p, root, force_container=container, update=update_lock,
                                     with_torch=with_torch or p.gpu))
    except (EnvironmentError, OSError, ValueError) as error:
        fail(str(error))


@app.command('init')
def initialize_environment(
    profile: str = typer.Argument('all', help='all 初始化 Humble 和 Jazzy CPU 环境'),
    root: Path = typer.Option(DEFAULT_ROOT, '--root'),
    workspace: Path = typer.Option(Path('.'), '--workspace'),
    container: bool = typer.Option(False, '--container'),
    update_lock: bool = typer.Option(False, '--update-lock'),
    with_torch: bool = typer.Option(False, '--with-torch'),
):
    """一键准备两套环境：合格宿主机直接复用，否则创建持久容器。"""
    try:
        names = ['ros2-humble-dev', 'ros2-jazzy-dev'] if profile == 'all' else [profile]
        for name in names:
            p = get_profile(name)
            show_result(containers.initialize(p, root, workspace, force_container=container,
                                              update=update_lock, with_torch=with_torch or p.gpu))
    except (EnvironmentError, OSError, ValueError) as error:
        fail(str(error))


@app.command('shell')
def shell_environment(
    profile: str, root: Path = typer.Option(DEFAULT_ROOT, '--root'),
    workspace: Path = typer.Option(Path('.'), '--workspace'),
    container: bool = typer.Option(False, '--container'),
    with_torch: bool = typer.Option(False, '--with-torch'),
):
    """进入本机或容器的开发终端，自动加载所选 ROS。"""
    try:
        p = get_profile(profile)
        containers.shell(p, root, workspace, force_container=container, with_torch=with_torch or p.gpu)
    except (EnvironmentError, OSError, ValueError) as error:
        fail(str(error))


@app.command('verify')
def verify_environment(
    profile: str, root: Path = typer.Option(DEFAULT_ROOT, '--root'),
    workspace: Path = typer.Option(Path('.'), '--workspace'),
    container: bool = typer.Option(False, '--container'),
    with_torch: bool = typer.Option(False, '--with-torch'),
):
    """真实生成并构建测试 ROS 模板；GPU 额外执行 CUDA 运算，保存验收记录。"""
    try:
        p = get_profile(profile)
        show_result(containers.verify(p, root, workspace, force_container=container,
                                      with_torch=with_torch or p.gpu))
    except (EnvironmentError, OSError, ValueError) as error:
        fail(str(error))


@app.command('containers')
def list_containers(profile: str = typer.Argument('ros2-jazzy-dev'),
                    as_json: bool = typer.Option(False, '--json')):
    """读取已有运行/停止的容器及兼容性和挂载；不自动启动。"""
    try:
        from rdk_cli.environments.discovery import discover
        containers.require_docker()
        candidates = discover(get_profile(profile))
        if as_json:
            typer.echo(json.dumps([c.data() for c in candidates], ensure_ascii=False, indent=2))
        else:
            table = Table(title='已有容器（停止状态需启动后进一步验证）')
            for label in ('容器', '镜像', '状态', '兼容', '挂载 / 说明'):
                table.add_column(label)
            for c in candidates:
                bindings = '\n'.join(f"{m['source']} → {m['target']} ({'rw' if m['writable'] else 'ro'})" for m in c.mounts)
                table.add_row(c.name, c.image, '运行中' if c.running else '已停止',
                              '候选' if c.compatible else '不匹配', bindings + '\n' + c.detail)
            console.print(table)
    except (EnvironmentError, OSError, ValueError) as error:
        fail(str(error))
