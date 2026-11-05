"""中文命令行帮助与参数错误；保留 Typer 的解析规则和退出码。"""
from io import StringIO
import re

import typer
from typer import core
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# 新版 Typer 内置 Click，旧版使用外部 Click；异常类型必须与实际解析器一致。
click = getattr(core, 'click', None) or core._click


def _translate(message: str) -> str:
    """只翻译框架文案，命令名、选项名和用户输入保持原样。"""
    replacements = {
        'Show this message and exit.': '显示帮助并退出。',
        'Install completion for the current shell.': '为当前终端安装命令补全。',
        'Install completion for the specified shell.': '为指定终端安装命令补全。',
        'Show completion for the current shell, to copy it or customize the installation.':
            '显示当前终端的补全脚本，方便复制或自定义安装。',
        'Show completion for the specified shell, to copy it or customize the installation.':
            '显示指定终端的补全脚本，方便复制或自定义安装。',
    }
    for source, target in replacements.items():
        message = message.replace(source, target)
    patterns = [
        (r'\[default:', '[默认：'),
        (r'\[required\]', '[必填]'),
        (r'\[env var:', '[环境变量：'),
        (r"No such command ('[^']*')\.", r'未知命令：\1。'),
        (r" Did you mean (.+)\?", r' 你可能想输入：\1。'),
        (r'Got unexpected extra argument(?:s|\(s\))?', '存在多余参数'),
        (r"Option ('[^']*') requires an argument\.", r'选项 \1 需要提供一个值。'),
        (r"('.*?') is not a valid (?:integer|int)\.", r'\1 不是有效的整数。'),
        (r"('.*?') is not a valid float\.", r'\1 不是有效的数值。'),
        (r"('.*?') is not a valid (?:boolean|bool)\.", r'\1 不是有效的布尔值。'),
        (r' is not one of ', ' 不在允许值中：'),
    ]
    for pattern, replacement in patterns:
        message = re.sub(pattern, replacement, message)
    return message


def _usage(ctx) -> str:
    usage = ctx.get_usage().replace('Usage:', '用法：', 1)
    return usage.replace('[OPTIONS]', '[选项]').replace('COMMAND', '命令').replace('[ARGS]', '[参数]')


def _error_message(error) -> str:
    if isinstance(error, click.exceptions.NoSuchOption):
        message = f'无法识别选项：{error.option_name}'
        if error.possibilities:
            message += '\n你可能想输入：' + '、'.join(error.possibilities)
        return message
    if isinstance(error, click.exceptions.BadParameter):
        hint = error.param_hint
        if not hint and error.param is not None:
            hint = error.param.get_error_hint(error.ctx)
        if isinstance(hint, (list, tuple)):
            hint = ' / '.join(hint)
        if isinstance(error, click.exceptions.MissingParameter):
            return f'缺少必填参数：{hint or "请查看帮助"}'
        return f'参数 {hint or ""} 的值无效：{_translate(error.message)}'
    return _translate(error.format_message())


class _ChineseError(click.ClickException):
    """仅替换展示方式，退出码继承原始解析错误。"""

    def __init__(self, original):
        super().__init__(original.message)
        self.original = original
        self.exit_code = original.exit_code

    def show(self, file=None):
        console = Console(file=file, stderr=file is None, markup=False)
        ctx = getattr(self.original, 'ctx', None)
        if self.original.__class__.__name__ == 'NoArgsIsHelpError':
            console.print(self.original.format_message(), end='\n')
            return
        if ctx is not None:
            console.print(_usage(ctx))
            console.print(f"输入 '{ctx.command_path} --help' 查看帮助。")
        console.print(Panel(Text(_error_message(self.original)), title='错误',
                            title_align='left', border_style='red'))


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
                    table.add_row(Text(record[0], style='cyan'), Text(_translate(record[1])))
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
    """在 Typer 原有异常处理之前适配错误，保持退出码和资源清理行为。"""

    def make_context(self, *args, **kwargs):
        try:
            return super().make_context(*args, **kwargs)
        except click.ClickException as error:
            if isinstance(error, _ChineseError):
                raise
            raise _ChineseError(error) from error

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except click.ClickException as error:
            if isinstance(error, _ChineseError):
                raise
            raise _ChineseError(error) from error


class ChineseTyper(typer.Typer):
    """让每个命令组自动使用中文展示，参数解析仍由 Typer 完成。"""

    def __init__(self, **kwargs):
        kwargs.setdefault('cls', ChineseGroup)
        # 错误由 _ChineseError.show 渲染，避免再次套用英文 Rich 错误面板。
        kwargs.setdefault('rich_markup_mode', None)
        super().__init__(**kwargs)

    def command(self, *args, **kwargs):
        kwargs.setdefault('cls', ChineseCommand)
        return super().command(*args, **kwargs)
