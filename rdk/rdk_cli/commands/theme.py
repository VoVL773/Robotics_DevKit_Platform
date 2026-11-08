"""配色主题命令：查看内置主题、切换并保存到用户配置。"""

import os

from rdk_cli.cli_locale import ChineseTyper

from rdk_cli import terminal as ui
from rdk_cli import theme
from rdk_cli.commands.common import fail

app = ChineseTyper(help='查看与切换终端配色主题。', no_args_is_help=True)


@app.command('list')
def theme_list():
    """列出全部内置主题，并标记当前选择。"""
    ui.themes(theme.active_name())


@app.command('show')
def theme_show():
    """展示当前主题的关键颜色、色块与配置文件位置。"""
    ui.theme_detail(theme.active())


@app.command('set')
def theme_set(name: str):
    """切换主题并保存；全屏工作台下次启动时生效。"""
    try:
        spec = theme.set_active(name)
    except theme.ThemeError as error:
        fail(str(error))
    ui.notice(f'已切换主题：{spec.label}（{spec.name}），新启动的 CLI 与全屏界面将使用该配色。',
              'success')
    ui.notice(f'配置文件：{theme.config_path()}', 'muted')
    if os.environ.get(theme.ENV_VAR):
        ui.notice(f'环境变量 {theme.ENV_VAR} 优先于配置文件，当前会话主题可能不会改变。', 'warning')
