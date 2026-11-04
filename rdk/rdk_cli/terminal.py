"""统一终端样式：真实终端显示高亮，重定向时自动移除颜色。"""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(highlight=False)


def menu():
    content = Table.grid(padding=(0, 2))
    content.add_column(style='bold cyan', no_wrap=True)
    content.add_column(style='bold white')
    content.add_column(style='dim')
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
    console.print(Panel(content, title='[bold cyan]Robotics DevKit[/bold cyan] · CLI 1.1',
                        subtitle='[dim]输入编号选择 · Ctrl+C 退出[/dim]',
                        border_style='cyan', padding=(1, 2), expand=False))


def templates(records, selectable=False):
    table = Table(title='选择项目模板' if selectable else '已安装模板',
                  box=box.ROUNDED, border_style='cyan', header_style='bold cyan',
                  show_lines=True, expand=False)
    if selectable:
        table.add_column('编号', style='bold yellow', no_wrap=True)
    table.add_column('模板 / 版本', style='bold cyan', no_wrap=True)
    if not selectable:
        table.add_column('发布状态', no_wrap=True)
        table.add_column('启用状态', no_wrap=True)
    table.add_column('说明')
    for index, record in enumerate(records, 1):
        row = [Text(f"{record['name']}@{record['version']}", style='bold cyan')]
        if selectable:
            row.insert(0, str(index))
        else:
            published = record['status'] == 'published'
            row.extend([
                Text('已发布' if published else '草稿', style='green' if published else 'yellow'),
                Text('已启用' if record['enabled'] else '已停用',
                     style='green' if record['enabled'] else 'dim'),
            ])
        row.append(Text(record['description']))
        table.add_row(*row)
    console.print(table)


def step(number, title):
    console.print()
    console.rule(Text(f'{number}  {title}', style='bold cyan'), align='left', style='cyan')


def notice(message, style='yellow'):
    console.print(Text(message, style=style))


def summary(record, values, output, git, ci, smoke):
    table = Table.grid(padding=(0, 2))
    table.add_column(style='dim', no_wrap=True)
    table.add_column()
    table.add_row('模板版本', Text(f"{record['name']}@{record['version']}", style='bold cyan'))
    labels = {'package_name': '项目名称', 'node_name': '节点名称', 'maintainer': '维护者',
              'maintainer_email': '维护者邮箱', 'license': '许可证', 'ros_distro': 'ROS 发行版'}
    for key, value in values.items():
        table.add_row(labels.get(key, key), Text(str(value)))
    table.add_row('生成位置', Text(output))
    table.add_row('Git / CI', f"{'创建' if git else '跳过'} / {'生成' if ci else '跳过'}")
    table.add_row('构建测试', '执行' if smoke else '跳过')
    console.print(Panel(table, title='[bold yellow]创建前确认[/bold yellow]',
                        border_style='yellow', expand=False))


def success(path, reference):
    content = Text('项目创建成功：', style='bold green')
    content.append(str(path), style='bold')
    content.append('\n模板版本：', style='dim')
    content.append(reference, style='cyan')
    console.print(Panel(content, title='[bold green]生成完成[/bold green]',
                        border_style='green', expand=False))
