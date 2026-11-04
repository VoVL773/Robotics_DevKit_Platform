"""模板管理命令：展示、创建、导入、启停和发布。"""
import json
from pathlib import Path
from typing import Optional

import typer

from rdk_cli import template_store as store
from rdk_cli import terminal as ui
from rdk_cli.commands.common import fail

app = typer.Typer(help='新建、导入、查看、启停与发布模板。', no_args_is_help=True)


@app.command('list')
def template_list():
    """列出所有已安装版本及启停、发布状态。"""
    try:
        ui.templates(store.inventory())
    except (store.TemplateError, OSError) as error:
        fail(str(error))


@app.command('info')
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
        fail(str(error))


@app.command('create')
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
        fail(str(error))


@app.command('install')
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
        fail(str(error))


@app.command('publish')
def template_publish(name: str, reviewed_by: str = typer.Option(..., '--reviewed-by')):
    """完成线下评审后记录评审人，发布并启用该版本。"""
    try:
        record = store.publish(name, reviewed_by)
        typer.echo(f"已发布并启用：{record['name']}@{record['version']}")
    except (store.TemplateError, OSError) as error:
        fail(str(error))


@app.command('enable')
def template_enable(name: str):
    """启用已发布的模板版本。"""
    _toggle(name, True)


@app.command('disable')
def template_disable(name: str):
    """停用模板版本，不修改已生成的项目。"""
    _toggle(name, False)


def _toggle(name, enabled):
    try:
        record = store.set_enabled(name, enabled)
        typer.echo(f"已{'启用' if enabled else '停用'}：{record['name']}@{record['version']}")
    except (store.TemplateError, OSError) as error:
        fail(str(error))
