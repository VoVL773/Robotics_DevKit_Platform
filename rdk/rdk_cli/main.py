"""robot-cli v1.1：管理模板版本、参数与项目生成。"""

import json
import re
import shlex
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import typer

from rdk_cli.environment import check_environment
from rdk_cli import template_store as store
from rdk_cli import terminal as ui

app = typer.Typer(help='robot-cli v1.1：版本化模板管理与 ROS 2 / PyTorch 项目生成。')
template_app = typer.Typer(help='新建、导入、查看、启停与发布模板。', no_args_is_help=True)
project_app = typer.Typer(help='从固定版本模板创建独立项目。', no_args_is_help=True)
app.add_typer(template_app, name='template')
app.add_typer(project_app, name='project')


def _fail(message):
    typer.secho(f'错误：{message}', fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


@template_app.command('list')
def template_list():
    """列出所有已安装版本及启停、发布状态。"""
    try:
        ui.templates(store.inventory())
    except (store.TemplateError, OSError) as error:
        _fail(str(error))


@template_app.command('info')
def template_info(name: str):
    """查看模板元数据、依赖、变更日志和参数。"""
    try:
        record = store.resolve(name)
        data = {key: str(value) if isinstance(value, Path) else value for key, value in record.items()}
        if ui.console.is_terminal:
            ui.console.print_json(data=data, ensure_ascii=False)
        else:
            typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    except (store.TemplateError, OSError) as error:
        _fail(str(error))


@template_app.command('create')
def template_create(
    name: str,
    version: str = typer.Option('0.1.0', '--version'),
    maintainer: str = typer.Option(..., '--maintainer'),
    kind: str = typer.Option('directory', '--kind', help='directory / ros2_python / ros2_cpp / ros2_bringup / pytorch'),
):
    """新建草稿模板目录和 template.json；编辑后评审发布。"""
    try:
        destination = store.create_draft(name, version, maintainer, kind)
        typer.echo(f'草稿已创建（停用）：{destination}\n编辑文件后使用 template publish 记录评审。')
    except (store.TemplateError, OSError) as error:
        _fail(str(error))


@template_app.command('install')
def template_install(
    source: str = typer.Argument(..., help='模板本地目录、Git URL 或注册表中的 name@version'),
    ref: Optional[str] = typer.Option(None, '--ref', help='Git 分支、标签或提交'),
    subdir: str = typer.Option('.', '--subdir', help='模板在 Git 仓库中的相对目录'),
    registry: Optional[str] = typer.Option(None, '--registry', help='JSON 注册表文件或 HTTP(S) URL'),
):
    """获取外部模板，作为停用草稿安装，已有版本不可覆盖。"""
    try:
        destination = store.import_template(source, ref, subdir, registry)
        typer.echo(f'模板已导入为停用草稿：{destination}\n请检查内容并完成评审后发布。')
    except (store.TemplateError, OSError) as error:
        _fail(str(error))


@template_app.command('publish')
def template_publish(name: str, reviewed_by: str = typer.Option(..., '--reviewed-by')):
    """完成线下评审后记录评审人，发布并启用该版本。"""
    try:
        record = store.publish(name, reviewed_by)
        typer.echo(f"已发布并启用：{record['name']}@{record['version']}")
    except (store.TemplateError, OSError) as error:
        _fail(str(error))


@template_app.command('enable')
def template_enable(name: str):
    """启用已发布的模板版本。"""
    _toggle(name, True)


@template_app.command('disable')
def template_disable(name: str):
    """停用模板版本，不修改已生成的项目。"""
    _toggle(name, False)


def _toggle(name, enabled):
    try:
        record = store.set_enabled(name, enabled)
        typer.echo(f"已{'启用' if enabled else '停用'}：{record['name']}@{record['version']}")
    except (store.TemplateError, OSError) as error:
        _fail(str(error))


def render_template(record, destination, values):
    """仅进行文本替换与文件复制；禁止符号链接、路径越界和未解析的占位符。"""
    root = record['path']
    rendered = {}
    def replace(text):
        for key, value in values.items():
            text = text.replace('{{' + key + '}}', str(value))
        if re.search(r'\{\{[a-z][a-z0-9_]*\}\}', text):
            raise store.TemplateError('模板包含未定义的参数占位符')
        return text

    for source in sorted(root.rglob('*')):
        relative = source.relative_to(root)
        if any(part in {'.git', '__pycache__'} for part in relative.parts) or source.suffix == '.pyc':
            continue
        if relative == Path('template.json'):
            continue
        if source.is_symlink():
            raise store.TemplateError(f'模板包含不支持的符号链接：{relative}')
        target = destination / replace(str(relative))
        if not target.resolve().is_relative_to(destination.resolve()):
            raise store.TemplateError(f'模板路径越界：{relative}')
        if source.is_dir():
            continue
        if not source.is_file():
            raise store.TemplateError(f'模板包含特殊文件：{relative}')
        if target in rendered:
            raise store.TemplateError(f'参数替换后路径重复：{relative}')
        content = source.read_bytes()
        try:
            content = replace(content.decode('utf-8')).encode('utf-8')
        except UnicodeDecodeError:
            pass
        rendered[target] = content
    # 先校验全部内容，再写入，避免模板错误留下半成品。
    for target, content in rendered.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _runtime_dependencies(project_path, kind):
    package_xml = project_path / 'package.xml'
    tree = ET.parse(package_xml)
    root = tree.getroot()
    dependencies = ['launch_ros', 'ament_index_python']
    if kind == 'ros2_bringup':
        dependencies += ['demo_nodes_cpp', 'python3-yaml']
    for dependency in dependencies:
        if not any(child.text == dependency for child in root if child.tag in {'depend', 'exec_depend'}):
            ET.SubElement(root, 'exec_depend').text = dependency
    tests = {'ros2_cpp': 'ament_cmake_gtest', 'ros2_python': 'python3-pytest',
             'ros2_bringup': 'ament_cmake_pytest'}
    if not any(child.text == tests[kind] for child in root):
        ET.SubElement(root, 'test_depend').text = tests[kind]
    # ros2 pkg create 生成的版权/style 占位测试与本模板无关；由行为测试替代。
    test_dir = project_path / 'test'
    for filename in ('test_copyright.py', 'test_flake8.py', 'test_pep257.py'):
        (test_dir / filename).unlink(missing_ok=True)
    ET.indent(tree, space='  ')
    tree.write(package_xml, encoding='utf-8', xml_declaration=True)


def _ci(kind):
    ros = kind.startswith('ros2_')
    if ros:
        return '''name: ROS smoke
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-24.04
    container: ros:jazzy-ros-base
    steps:
      - uses: actions/checkout@v4
        with:
          path: ws/src/project
      - name: Build and test
        shell: bash
        run: |
          source /opt/ros/jazzy/setup.bash
          apt-get update
          apt-get install -y python3-colcon-common-extensions python3-rosdep python3-pytest
          cd ws
          rosdep update
          rosdep install --from-paths src --ignore-src -r -y
          colcon build --symlink-install
          source install/setup.bash
          colcon test --event-handlers console_direct+
          colcon test-result --verbose
'''
    return '''name: CPU smoke
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install -e '.[dev]'
      - run: python -m pytest -q
      - run: python -m training.train
      - run: python -m training.evaluate
'''


@project_app.command('create')
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
        record = store.resolve(template, usable=True)
        supplied = {'package_name': name}
        for key, value in [('node_name', node_name), ('maintainer', maintainer),
                           ('maintainer_email', maintainer_email), ('license', license),
                           ('ros_distro', ros_distro)]:
            if value is not None:
                supplied[key] = value
        for item in param or []:
            key, separator, value = item.partition('=')
            if not separator or key in supplied:
                raise store.TemplateError(f'模板参数应为 KEY=VALUE 且不能重复：{item}')
            supplied[key] = value
        # 即使自定义模板没有 package_name 的 pattern，输出目录也必须保持安全。
        if not re.fullmatch(r'[a-z](?:[a-z0-9_]*[a-z0-9])?', name):
            raise store.TemplateError('项目名必须以小写字母开头，只能包含小写字母、数字和下划线，且不能以下划线结尾')
        values = store.parameters(record, supplied)
        kind = record['kind']
        if ci and kind == 'directory':
            raise store.TemplateError('通用 directory 模板需要自行提供 CI；--ci 仅支持 ROS/PyTorch')
        if smoke_test and kind == 'directory':
            raise store.TemplateError('通用 directory 模板需要自行执行测试')
        output_path = Path(output).expanduser().resolve()
        project_path = output_path / name
        if project_path.exists() or project_path.is_symlink():
            raise store.TemplateError(f'目标路径已经存在：{project_path}')
        if kind.startswith('ros2_'):
            check_environment()
            command = ['ros2', 'pkg', 'create', name,
                       '--build-type', 'ament_python' if kind == 'ros2_python' else 'ament_cmake',
                       '--license', values.get('license', 'Apache-2.0'),
                       '--maintainer-name', values.get('maintainer', 'contributor'),
                       '--maintainer-email', values.get('maintainer_email', 'maintainer@example.com'),
                       '--destination-directory', str(output_path)]
            if kind != 'ros2_bringup':
                command += ['--dependencies', 'rclpy' if kind == 'ros2_python' else 'rclcpp',
                            '--node-name', values.get('node_name', 'hello_node')]
            output_path.mkdir(parents=True, exist_ok=True)
            subprocess.run(command, check=True)
        else:
            project_path.mkdir(parents=True, exist_ok=False)
        render_values = {**values, 'template_id': record['name'], 'template_version': record['version'],
                         'package_name_upper': name.upper(), 'language': record.get('language', kind)}
        render_template(record, project_path, render_values)
        if kind.startswith('ros2_'):
            _runtime_dependencies(project_path, kind)
        store.save_json(project_path / '.robot-cli.json', {
            'template': record['name'], 'version': record['version'], 'parameters': values,
            'source': record.get('source', 'builtin'), 'cli_version': '1.1.0',
        })
        if ci:
            workflow = project_path / '.github/workflows/smoke.yml'
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(_ci(kind), encoding='utf-8')
        if git:
            subprocess.run(['git', 'init', str(project_path)], check=True)
        ui.success(project_path, f"{record['name']}@{record['version']}")
        ui.notice('下一步', 'bold cyan')
        if kind.startswith('ros2_'):
            workspace = output_path.parent if output_path.name == 'src' else output_path
            typer.echo(f'  cd {shlex.quote(str(workspace))}')
            typer.echo(f'  colcon build --symlink-install --packages-select {name}')
            typer.echo('  source install/setup.bash')
            launch = 'bringup.launch.py' if kind == 'ros2_bringup' else 'hello.launch.py'
            typer.echo(f'  ros2 launch {name} {launch}')
            if smoke_test:
                subprocess.run(['colcon', 'build', '--symlink-install', '--packages-select', name],
                               cwd=workspace, check=True)
                # 加载刚安装的包，使 ament 索引测试能找到资源。
                script = ('source install/setup.bash && colcon test --packages-select ' + shlex.quote(name)
                          + ' --event-handlers console_direct+ && colcon test-result --verbose')
                subprocess.run(['bash', '-c', script], cwd=workspace, check=True)
        elif kind == 'pytorch':
            typer.echo(f'  cd {shlex.quote(str(project_path))}')
            typer.echo("  python3 -m venv .venv && source .venv/bin/activate")
            typer.echo("  python -m pip install -e '.[dev]'")
            typer.echo('  python -m training.train --config configs/default.json')
            typer.echo('  python -m training.evaluate --checkpoint outputs/checkpoint.pt')
            if smoke_test:
                import sys
                for command in ([sys.executable, '-m', 'pytest', '-q'],
                                [sys.executable, '-m', 'training.train'],
                                [sys.executable, '-m', 'training.evaluate']):
                    subprocess.run(command, cwd=project_path, check=True)
        if smoke_test:
            ui.notice('✓ 冒烟测试通过。', 'bold green')
    except (store.TemplateError, OSError, ET.ParseError) as error:
        _fail(str(error))
    except subprocess.CalledProcessError as error:
        _fail(f'外部命令失败，退出码 {error.returncode}。已生成文件保留，请检查日志和依赖后重试。')



def interactive_wizard():
    """裸命令进入终端菜单；成功创建后返回并自动退出。"""
    while True:
        ui.menu()
        action = typer.prompt(typer.style('请选择', fg=typer.colors.CYAN, bold=True), default='1')
        if action == '0':
            return
        if action == '2':
            template_list()
            reference = typer.prompt('查看详情（留空返回）', default='', show_default=False)
            if reference:
                template_info(reference)
            continue
        if action in {'4', '5', '7'}:
            reference = typer.prompt('模板名称@版本')
            if action == '7':
                template_publish(reference, typer.prompt('已完成评审的评审人'))
            else:
                _toggle(reference, action == '4')
            continue
        if action == '3':
            template_create(typer.prompt('模板名称'), typer.prompt('版本', default='0.1.0'),
                            typer.prompt('维护者'), typer.prompt('类型', default='directory'))
            continue
        if action == '6':
            source = typer.prompt('本地模板目录、Git URL 或注册表引用')
            registry = typer.prompt('注册表路径/URL（留空表示直接来源）', default='', show_default=False)
            ref = typer.prompt('Git ref（留空使用默认版本）', default='', show_default=False)
            subdir = typer.prompt('模板子目录', default='.')
            template_install(source, ref or None, subdir, registry or None)
            continue
        if action != '1':
            ui.notice('请输入菜单中的数字。')
            continue
        try:
            available = [item for item in store.inventory() if item['status'] == 'published' and item['enabled']]
        except (store.TemplateError, OSError) as error:
            _fail(str(error))
        if not available:
            typer.echo('没有已启用的发布版本，请先导入、发布或启用模板。')
            continue
        ui.step('1 / 4', '选择模板')
        ui.templates(available, selectable=True)
        choice = typer.prompt('选择模板编号', type=int)
        if not 1 <= choice <= len(available):
            typer.echo('模板编号超出范围，请重新选择。')
            continue
        record = available[choice - 1]
        ui.step('2 / 4', '填写项目参数')
        ui.notice(f"已选择：{record['name']}@{record['version']}", 'bold green')
        supplied = {}
        for key, spec in record['parameters'].items():
            label = {
                'package_name': '项目名称', 'node_name': '节点名称', 'maintainer': '维护者',
                'maintainer_email': '维护者邮箱', 'license': '许可证', 'ros_distro': 'ROS 发行版',
            }.get(key, key)
            while True:
                default = spec.get('default', None if spec.get('required') else '')
                if default is not None and spec['type'] != 'string' and default != '':
                    default = json.dumps(default)
                value = typer.prompt(typer.style(label, fg=typer.colors.CYAN), default=default,
                                     type=str, show_default='default' in spec)
                if value == '' and not spec.get('required') and 'default' not in spec:
                    break
                try:
                    candidate = json.loads(value) if spec['type'] != 'string' else value
                    store.validate_value(key, candidate, spec)
                    if key == 'package_name' and (value in store.CPP_KEYWORDS or store.keyword.iskeyword(value)):
                        raise store.TemplateError('项目名不能使用 Python/C++ 关键字')
                except (store.TemplateError, ValueError) as error:
                    ui.notice(f'参数错误：{error}，请重新输入。', 'bold red')
                    continue
                supplied[key] = value
                break
        ui.step('3 / 4', '生成与验证选项')
        output = typer.prompt('生成位置（ROS 建议使用工作空间 src 目录）', default='.')
        initialize_git = typer.confirm('初始化 Git 仓库？', default=False)
        create_ci = typer.confirm('生成 GitHub Actions CI？', default=False) if record['kind'] != 'directory' else False
        run_smoke = typer.confirm('现在构建并执行冒烟测试（需已安装依赖）？', default=True) if record['kind'] != 'directory' else False
        ui.step('4 / 4', '确认并创建')
        ui.summary(record, supplied, output, initialize_git, create_ci, run_smoke)
        if not typer.confirm('确认创建？', default=True):
            continue
        project_create(
            template=f"{record['name']}@{record['version']}", name=supplied.pop('package_name'),
            output=output, node_name=None, maintainer=None, maintainer_email=None,
            license=None, ros_distro=None,
            param=[f'{key}={value}' for key, value in supplied.items()],
            git=initialize_git, ci=create_ci, smoke_test=run_smoke,
        )
        ui.notice('✓ 流程完成，退出 CLI。', 'bold green')
        return


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, '--version', help='显示 CLI 版本'),
    wizard: bool = typer.Option(False, '--wizard', help='使用逐步问答向导，兼容不支持全屏界面的终端'),
):
    if version:
        typer.echo('robot-cli 1.1.0')
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        if wizard:
            interactive_wizard()
            return
        import sys
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            _fail('全屏界面需要交互式终端；请直接在终端运行 robot-cli，或使用 --wizard / 子命令。')
        from rdk_cli.tui import DevKitApp
        result = DevKitApp().run()
        if result:
            typer.echo(result)


if __name__ == '__main__':
    app()
