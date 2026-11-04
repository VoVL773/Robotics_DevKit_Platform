"""CLI 装配入口：注册命令组，选择全屏工作台或旧问答向导。"""
import typer

from rdk_cli.commands.common import fail
from rdk_cli.commands.environments import app as env_app, doctor
from rdk_cli.commands.projects import app as project_app
from rdk_cli.commands.templates import app as template_app

app = typer.Typer(help='robot-cli v1.1：版本化模板管理与 ROS 2 / PyTorch 项目生成。')
app.add_typer(template_app, name='template')
app.add_typer(project_app, name='project')
app.add_typer(env_app, name='env')
app.command('doctor')(doctor)


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
            from rdk_cli.wizard import interactive_wizard
            interactive_wizard()
            return
        import sys
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            fail('全屏界面需要交互式终端；请直接在终端运行 robot-cli，或使用 --wizard / 子命令。')
        from rdk_cli.tui import DevKitApp
        result = DevKitApp().run()
        if result:
            typer.echo(result)


if __name__ == '__main__':
    app()
