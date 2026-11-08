"""统一终端样式：颜色由当前主题提供，重定向时自动移除颜色。"""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from rdk_cli import theme

console = Console(highlight=False)
error_console = Console(highlight=False, stderr=True)

COLOUR_KEYS = {
    'background': '背景',
    'surface': '面板',
    'panel': '标题栏',
    'accent': '强调',
    'border': '边框',
    'text': '正文',
    'muted': '次要文字',
    'error': '错误',
    'warning': '警告',
    'success': '成功',
}


def style(key='text', bold=False, dim=False):
    """返回当前主题颜色的 rich 样式字符串。"""
    parts = ['bold'] if bold else []
    parts += ['dim'] if dim else []
    parts.append(theme.active().colors[key])
    return ' '.join(parts)


def prompt_label(text, key='accent'):
    """把提示文字渲染为 ANSI 样式，交给 typer.prompt 显示。"""
    if not console.is_terminal:
        return text
    with console.capture() as capture:
        console.print(Text(text, style=style(key)))
    return capture.get().rstrip('\n')


def error(message):
    error_console.print(Text(f'错误：{message}', style=style('error', bold=True)))


def menu():
    content = Table.grid(padding=(0, 2))
    content.add_column(style=style('accent', bold=True), no_wrap=True)
    content.add_column(style=style('text', bold=True))
    content.add_column(style=style('muted', dim=True))
    for number, label, hint in [
        ('1', '创建项目', '选择模板，填写参数并构建'),
        ('2', '查看模板', '浏览版本、依赖与参数'),
        ('3', '新建模板', '创建团队模板草稿'),
        ('4', '启用模板', '启用已发布版本'),
        ('5', '停用模板', '保留模板与已有项目'),
        ('6', '导入模板', '本地目录 / Git / 注册表'),
        ('7', '评审发布', '记录评审并发布版本'),
        ('0', '退出', '结束本次操作'),
    ]:
        content.add_row(number, label, hint)
    console.print()
    console.print(Panel(content,
                        title=Text('Robotics DevKit', style=style('accent', bold=True)),
                        subtitle=Text('输入编号选择 · Ctrl+C 退出', style=style('muted')),
                        border_style=style('accent'), padding=(1, 2), expand=False))


def templates(records, selectable=False):
    table = Table(title='选择项目模板' if selectable else '已安装模板',
                  box=box.ROUNDED, border_style=style('border'),
                  header_style=style('accent', bold=True),
                  show_lines=True, expand=False)
    if selectable:
        table.add_column('编号', style=style('warning', bold=True), no_wrap=True)
    table.add_column('模板 / 版本', style=style('accent', bold=True), no_wrap=True)
    if not selectable:
        table.add_column('发布状态', no_wrap=True)
        table.add_column('启用状态', no_wrap=True)
    table.add_column('说明')
    for index, record in enumerate(records, 1):
        row = [Text(f"{record['name']}@{record['version']}", style=style('accent', bold=True))]
        if selectable:
            row.insert(0, str(index))
        else:
            published = record['status'] == 'published'
            row.extend([
                Text('已发布' if published else '草稿',
                     style=style('success' if published else 'warning')),
                Text('已启用' if record['enabled'] else '已停用',
                     style=style('success') if record['enabled'] else style('muted', dim=True)),
            ])
        row.append(Text(record['description'], style=style('text')))
        table.add_row(*row)
    console.print(table)


def themes(current):
    """列出内置主题，标记当前选择。"""
    table = Table(title='可用主题', box=box.ROUNDED, border_style=style('border'),
                  header_style=style('accent', bold=True), show_lines=True, expand=False)
    table.add_column('名称', no_wrap=True)
    table.add_column('标识', no_wrap=True)
    table.add_column('说明')
    table.add_column('状态', no_wrap=True)
    for spec in theme.THEMES.values():
        table.add_row(Text(spec.label, style=style('accent', bold=True)),
                      Text(spec.name, style=style('muted')),
                      Text(spec.description, style=style('text')),
                      Text('当前' if spec.name == current else '',
                           style=style('success', bold=True)))
    console.print(table)


def theme_detail(spec):
    """展示当前主题的关键颜色与配置位置。"""
    table = Table.grid(padding=(0, 2))
    table.add_column(style=style('muted', dim=True), no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column()
    for key, label in COLOUR_KEYS.items():
        value = spec.colors[key]
        table.add_row(label, Text(value, style=style('text')),
                      Text('   ', style=f'on {value}'))
    console.print(Panel(table,
                        title=Text(f'当前主题：{spec.label}（{spec.name}）',
                                   style=style('accent', bold=True)),
                        border_style=style('border'), expand=False))
    console.print(Text(f'配置文件：{theme.config_path()}', style=style('muted')))


def step(number, title):
    console.print()
    console.rule(Text(f'{number}  {title}', style=style('accent', bold=True)),
                 align='left', style=style('accent'))


def notice(message, tone='warning'):
    console.print(Text(message, style=style(tone, bold=tone in {'success', 'error'})))


def summary(record, values, output, git, ci, smoke, examples=True):
    table = Table.grid(padding=(0, 2))
    table.add_column(style=style('muted', dim=True), no_wrap=True)
    table.add_column()
    table.add_row('模板版本', Text(f"{record['name']}@{record['version']}",
                                   style=style('accent', bold=True)))
    labels = {'package_name': '项目名称', 'node_name': '节点名称', 'maintainer': '维护者',
              'maintainer_email': '维护者邮箱', 'license': '许可证', 'ros_distro': 'ROS 发行版'}
    for key, value in values.items():
        table.add_row(labels.get(key, key), Text(str(value)))
    table.add_row('生成位置', Text(output))
    table.add_row('Git / CI', f"{'创建' if git else '跳过'} / {'生成' if ci else '跳过'}")
    table.add_row('示例代码', '生成示例代码' if examples else '不生成示例代码（工程骨架）')
    table.add_row('构建测试', '执行' if smoke else '跳过')
    console.print(Panel(table, title=Text('创建前确认', style=style('warning', bold=True)),
                        border_style=style('warning'), expand=False))


def success(path, reference):
    content = Text('项目创建成功：', style=style('success', bold=True))
    content.append(str(path), style=style('text', bold=True))
    content.append('\n模板版本：', style=style('muted', dim=True))
    content.append(reference, style=style('accent'))
    console.print(Panel(content, title=Text('生成完成', style=style('success', bold=True)),
                        border_style=style('success'), expand=False))
