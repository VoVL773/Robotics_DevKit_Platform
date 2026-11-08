"""工作台布局与样式；控件 ID 是界面控制器与布局之间的约定。"""
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button, Checkbox, Collapsible, DataTable, Footer, Header, Input, Label,
    LoadingIndicator, RichLog, Select, Static, TabbedContent, TabPane,
)

from rdk_cli import template_store as store
from rdk_cli import theme as palette

WORKBENCH_CSS = '''
    Screen { background: $background; color: $foreground; }
    Header { background: $panel; color: $rdk-header-text; }
    Footer { background: $panel; }
    Tabs { background: $rdk-tabbar; }
    Tab.-active { color: $primary; background: $rdk-tabbar; text-style: bold; }
    Underline > .underline--bar { color: $accent; background: $accent; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 2; }
    .heading { color: $primary; text-style: bold; margin-bottom: 1; height: auto; }
    .hint { color: $rdk-muted; height: auto; margin-bottom: 1; }
    #create-layout { height: 1fr; }
    #template-sidebar { width: 36; min-width: 24; border: round $secondary; padding: 1; margin-right: 2; }
    #project-panel { width: 1fr; min-width: 30; border: round $secondary; }
    #project-form { height: 1fr; padding: 1 2; }
    #project-actions { padding: 0 2 1 2; margin: 0; }
    Screen.compact TabPane { padding: 0 1; }
    Screen.compact #template-sidebar { width: 25; min-width: 20; padding: 0 1; margin-right: 1; }
    Screen.compact #project-panel { min-width: 26; }
    Screen.compact #project-form { padding: 0 1; }
    Screen.compact #project-actions { padding: 0 1; }
    #template-description { height: auto; margin-top: 1; }
    Label { height: auto; margin-top: 1; color: $rdk-muted; }
    Input, Select { width: 1fr; margin-top: 0; }
    Input:focus { border: tall $primary; }
    #parameters { height: auto; }
    .buttons { height: auto; margin-top: 1; }
    Button { margin-right: 1; }
    Checkbox { margin: 0; height: auto; }
    #project-error { height: auto; color: $error; margin-top: 1; }
    #job-status { height: auto; background: $rdk-job-bg; padding: 0 2; color: $primary; }
    #template-table { height: 10; border: round $secondary; }
    #template-detail { height: auto; padding: 1; border: round $secondary; margin-top: 1; }
    .form-section { height: auto; padding: 0 1 1 1; }
    #management-message { height: auto; color: $primary; margin-top: 1; }
    #environment-report { height: auto; border: round $secondary; padding: 1 2; }
    #build-log { height: 1fr; border: round $secondary; background: $rdk-log-bg; }
    #running { height: 1; display: none; }
    #running.visible { display: block; }
    #log-heading { height: auto; }
    '''

def compose_workbench() -> ComposeResult:
    yield Header()
    with TabbedContent(initial='create-tab', id='tabs'):
        with TabPane('项目创建', id='create-tab'):
            with Horizontal(id='create-layout'):
                with VerticalScroll(id='template-sidebar'):
                    yield Static('01  选择模板', classes='heading')
                    yield Static('先选模板，再选版本。已有项目不会被覆盖。', classes='hint')
                    yield Label('模板')
                    yield Select([], prompt='请选择模板', id='project-template')
                    yield Label('版本')
                    yield Select([], prompt='请选择版本', id='project-version')
                    yield Static('', id='template-description', markup=False)
                with Vertical(id='project-panel'):
                    with VerticalScroll(id='project-form'):
                        yield Static('02  项目配置', classes='heading')
                        with Vertical(id='parameters'):
                            yield Static('正在加载模板…')
                        yield Label('生成位置（ROS 建议选择工作空间 src 目录）')
                        yield Input(str(Path.cwd()), id='output')
                        yield Label('示例代码')
                        yield Select([('生成示例代码', 'yes'), ('不生成示例代码', 'no')],
                                     value='yes', allow_blank=False, id='project-examples')
                        yield Checkbox('初始化 Git 仓库', id='git')
                        yield Checkbox('生成 GitHub Actions CI', id='ci')
                        yield Checkbox('构建并执行冒烟测试（需提前安装依赖）', id='smoke')
                        yield Checkbox('成功后自动退出', value=True, id='auto-exit')
                        yield Static('同发行版本机直接创建；环境不符时配置或复用容器。', classes='hint')
                        with Collapsible(title='容器环境 / 已有容器', collapsed=True, id='container-settings'):
                            yield Checkbox('使用容器创建和构建', id='use-container')
                            yield Button('读取已有容器', id='scan-containers')
                            yield Select([('新建独立开发容器', 'new')], value='new', allow_blank=False, id='existing-container')
                            yield Static('', id='container-report', markup=False)
                            yield Label('新建容器名（留空自动命名）')
                            yield Input(placeholder='rdk-humble-demo', id='container-name')
                            yield Label('宿主机挂载目录（留空使用生成位置 → /workspace）')
                            yield Input(placeholder='须包含项目生成位置；已有容器使用既有挂载', id='container-mount')
                        yield Static('', id='project-error', markup=False)
                    with Horizontal(classes='buttons', id='project-actions'):
                        yield Button('创建项目', variant='primary', id='create-project')
                        yield Button('查看日志', id='view-logs')
        with TabPane('模板管理', id='manage-tab'):
            with VerticalScroll():
                yield Static('模板版本与发布状态', classes='heading')
                yield DataTable(id='template-table', cursor_type='row')
                with Horizontal(classes='buttons'):
                    yield Button('启用版本', variant='success', id='enable-template')
                    yield Button('停用版本', variant='warning', id='disable-template')
                    yield Button('刷新', id='refresh-templates')
                yield Static('', id='template-detail', markup=False)
                yield Label('评审人（完成团队评审后填写）')
                yield Input(placeholder='reviewer@example.com', id='reviewer')
                yield Button('记录评审并发布', id='publish-template', variant='primary')
                yield Static('', id='management-message', markup=False)
                with Collapsible(title='新建团队模板', collapsed=True):
                    with Vertical(classes='form-section'):
                        yield Label('模板名称')
                        yield Input(placeholder='team-demo', id='draft-name')
                        yield Label('版本')
                        yield Input('0.1.0', id='draft-version')
                        yield Label('维护者')
                        yield Input(placeholder='Robot Team', id='draft-maintainer')
                        yield Label('类型')
                        yield Select([(name, name) for name in sorted(store.KINDS)],
                                     value='directory', allow_blank=False, id='draft-kind')
                        yield Button('创建草稿', id='create-draft', variant='primary')
                with Collapsible(title='从本地 / Git / 注册表导入', collapsed=True):
                    with Vertical(classes='form-section'):
                        yield Label('模板目录、Git URL 或注册表模板引用')
                        yield Input(placeholder='目录 / Git URL / team-demo@1.0.0', id='import-source')
                        yield Label('注册表路径或 URL（可选）')
                        yield Input(id='import-registry')
                        yield Label('Git ref（可选）')
                        yield Input(id='import-ref')
                        yield Label('仓库内模板子目录')
                        yield Input('.', id='import-subdir')
                        yield Button('导入为草稿', id='import-template', variant='primary')
        with TabPane('环境检查', id='env-tab'):
            with VerticalScroll():
                yield Static('当前终端环境', classes='heading')
                yield Static('Humble 对应 Ubuntu 22.04；Jazzy 对应 Ubuntu 24.04；跨版本可使用容器。', classes='hint')
                yield Static('', id='environment-report', markup=False)
                yield Button('重新检查', id='check-environment', variant='primary')
                yield Static('界面主题', classes='heading')
                yield Static('切换后立即生效并记住选择；也可按 Ctrl+T 循环切换。', classes='hint')
                yield Select([(spec.label, spec.name) for spec in palette.THEMES.values()],
                             value=palette.active_name(), allow_blank=False, id='theme-select')
        with TabPane('构建日志', id='logs-tab'):
            yield Static('生成、构建与测试输出', id='log-heading', classes='heading')
            yield LoadingIndicator(id='running')
            yield RichLog(id='build-log', wrap=True, markup=False, max_lines=5000)
            with Horizontal(classes='buttons'):
                yield Button('取消任务', variant='error', id='cancel-task', disabled=True)
                yield Button('返回项目配置', id='back-to-form')
    yield Static('就绪 · 选择模板并填写项目参数', id='job-status', markup=False)
    yield Footer()
