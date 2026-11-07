"""兼容旧终端的逐步问答向导，独立于全屏 TUI 和主入口。"""
import json

import typer

from rdk_cli import template_store as store
from rdk_cli import terminal as ui
from rdk_cli.commands.common import fail
from rdk_cli.commands.projects import project_create
from rdk_cli.commands.templates import (
    template_list, template_info, template_publish, template_create, template_install, _toggle,
)


def interactive_wizard():
    """--wizard 进入终端菜单；成功创建后返回并自动退出。"""
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
            fail(str(error))
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
            label = spec.get('label', key)
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
        examples = typer.confirm('生成示例代码？（否：仅生成工程骨架）', default=True)
        initialize_git = typer.confirm('初始化 Git 仓库？', default=False)
        generation = record.get('generation', {})
        ci_key = 'ci' if examples else 'skeleton_ci'
        smoke_key = 'smoke_commands' if examples else 'skeleton_smoke_commands'
        create_ci = typer.confirm('生成 GitHub Actions CI？', default=False) if generation.get(ci_key) else False
        run_smoke = typer.confirm('现在构建并执行冒烟测试（需已安装依赖）？', default=True) if generation.get('smoke_engine') or generation.get(smoke_key) else False
        ui.step('4 / 4', '确认并创建')
        ui.summary(record, supplied, output, initialize_git, create_ci, run_smoke, examples=examples)
        if not typer.confirm('确认创建？', default=True):
            continue
        project_create(
            template=f"{record['name']}@{record['version']}", name=supplied.pop('package_name'),
            output=output, node_name=None, maintainer=None, maintainer_email=None,
            license=None, ros_distro=None,
            param=[f'{key}={value}' for key, value in supplied.items()],
            git=initialize_git, ci=create_ci, smoke_test=run_smoke, examples=examples,
            container=False, container_name=None, mount=None, env_root='.robot-cli/environments', host_only=False, reuse_container=None,
        )
        ui.notice('✓ 流程完成，退出 CLI。', 'bold green')
        return
