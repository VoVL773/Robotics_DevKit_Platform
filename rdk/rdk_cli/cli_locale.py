"""仅定制中文帮助；参数解析、异常类型和错误展示均交给原始框架。"""
from io import StringIO

import typer
from typer import core
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def _usage(ctx) -> str:
    usage = ctx.get_usage()
    return '用法：' + usage[len('Usage:'):] if usage.startswith('Usage:') else usage


class _ChineseHelp:
    """统一渲染根命令、命令组和子命令的帮助，不修改框架全局常量。"""

    def get_help(self, ctx):
        output = StringIO()
        console = Console(file=output, markup=False)
        console.print(_usage(ctx))
        if self.help:
            console.print(self.help)
        for title, option in [('参数', False), ('选项', True)]:
            table = Table.grid(padding=(0, 2))
            count = 0
            for param in self.get_params(ctx):
                if (param.param_type_name == 'option') != option or getattr(param, 'hidden', False):
                    continue
                record = param.get_help_record(ctx)
                if record:
                    description = record[1]
                    if param.name == 'help' and description == 'Show this message and exit.':
                        description = '显示帮助并退出。'
                    table.add_row(Text(record[0], style='cyan'), Text(description))
                    count += 1
            if count:
                console.print(Panel(table, title=title, title_align='left'))
        if isinstance(self, core.TyperGroup):
            table = Table.grid(padding=(0, 2))
            count = 0
            for name in self.list_commands(ctx):
                command = self.get_command(ctx, name)
                if command is not None and not command.hidden:
                    table.add_row(Text(name, style='cyan'), Text(command.get_short_help_str()))
                    count += 1
            if count:
                console.print(Panel(table, title='命令', title_align='left'))
        if self.epilog:
            console.print(self.epilog)
        return output.getvalue().rstrip('\n')


class ChineseCommand(_ChineseHelp, core.TyperCommand):
    """带中文帮助的普通命令。"""


class ChineseGroup(_ChineseHelp, core.TyperGroup):
    """只定制帮助，不拦截或包装框架异常。"""


class ChineseTyper(typer.Typer):
    """让每个命令组使用中文帮助，解析和错误处理保持框架原样。"""

    def __init__(self, **kwargs):
        kwargs.setdefault('cls', ChineseGroup)
        # 使用框架原生文本错误；帮助标题的中文仅由 get_help 提供。
        kwargs.setdefault('rich_markup_mode', None)
        super().__init__(**kwargs)

    def command(self, *args, **kwargs):
        kwargs.setdefault('cls', ChineseCommand)
        return super().command(*args, **kwargs)
