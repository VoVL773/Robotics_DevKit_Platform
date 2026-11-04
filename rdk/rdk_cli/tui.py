"""Textual 终端工作台：表单与模板管理复用现有逻辑，耗时任务运行在独立进程组中。"""

import importlib.metadata
import json
import shlex
import sys

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import (
    Button, Checkbox, DataTable, Input, Label,
    LoadingIndicator, RichLog, Select, Static, TabbedContent,
)

from rdk_cli.process_runner import ProcessRunner
from rdk_cli.project_service import ProjectRequest, prepare_project
from rdk_cli.tui_layout import WORKBENCH_CSS, compose_workbench
from rdk_cli import environment
from rdk_cli import template_store as store

LABELS = {
    'package_name': '项目名称', 'node_name': '节点名称', 'maintainer': '维护者',
    'maintainer_email': '维护者邮箱', 'license': '许可证', 'ros_distro': 'ROS 发行版',
}


class DevKitApp(App[str]):
    """中文终端界面；键盘、鼠标和脚本子命令使用相同的模板与参数规则。"""

    TITLE = 'Robotics DevKit'
    SUB_TITLE = '项目与模板工作台 · v1.1'
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding('f5', 'refresh', '刷新'),
        Binding('ctrl+l', 'show_logs', '构建日志'),
        Binding('ctrl+q', 'quit', '退出'),
        Binding('ctrl+c', 'quit', '退出', show=False),
    ]
    CSS = WORKBENCH_CSS

    def __init__(self):
        super().__init__()
        self.records = []
        self.project_record = None
        self.managed_reference = None
        self.runner = ProcessRunner()
        self.busy = False
        self.cancel_requested = False
        self.quit_requested = False
        self.parameter_keys = []
        self.last_project = None
        self.last_result = None

    def compose(self) -> ComposeResult:
        yield from compose_workbench()

    def on_resize(self, event):
        self.screen.set_class(event.size.width < 95, 'compact')

    async def on_mount(self):
        self.theme = 'textual-dark'
        table = self.query_one('#template-table', DataTable)
        table.add_columns('模板', '版本', '发布状态', '启用状态')
        await self.refresh_templates()
        self.refresh_environment()

    @staticmethod
    def reference(record):
        return f"{record['name']}@{record['version']}"

    async def refresh_templates(self):
        try:
            self.records = store.inventory()
        except (store.TemplateError, environment.EnvironmentCheckError, OSError) as error:
            self.message(str(error), error=True)
            return
        available = [record for record in self.records if record['enabled'] and record['status'] == 'published']
        selector = self.query_one('#project-template', Select)
        previous = selector.value
        with selector.prevent(Select.Changed):
            selector.set_options([(self.reference(record), self.reference(record)) for record in available])
            references = [self.reference(record) for record in available]
            selector.value = previous if previous in references else (references[0] if references else Select.BLANK)
        self.project_record = next((record for record in available if self.reference(record) == selector.value), None)
        await self.build_parameters()
        table = self.query_one('#template-table', DataTable)
        table.clear()
        for record in self.records:
            table.add_row(record['name'], record['version'],
                          Text('已发布' if record['status'] == 'published' else '草稿',
                               style='green' if record['status'] == 'published' else 'yellow'),
                          Text('已启用' if record['enabled'] else '已停用',
                               style='green' if record['enabled'] else 'dim'), key=self.reference(record))
        if self.managed_reference not in [self.reference(record) for record in self.records]:
            self.managed_reference = self.reference(self.records[0]) if self.records else None
        if self.managed_reference:
            table.move_cursor(row=next(index for index, record in enumerate(self.records)
                                       if self.reference(record) == self.managed_reference))
        self.show_template_detail()

    @on(Select.Changed, '#project-template')
    async def select_project_template(self, event):
        self.project_record = next((record for record in self.records if self.reference(record) == event.value), None)
        await self.build_parameters()

    async def build_parameters(self):
        container = self.query_one('#parameters', Vertical)
        # 刷新同一模板时保留已填参数；切换模板时按新 schema 初始化。
        previous = {key: self.query_one(f'#param-{key}').value for key in self.parameter_keys
                    if self.query(f'#param-{key}')}
        old_reference = getattr(self, '_form_reference', None)
        new_reference = self.reference(self.project_record) if self.project_record else None
        await container.remove_children()
        self.parameter_keys = []
        self._form_reference = new_reference
        description = self.query_one('#template-description', Static)
        if self.project_record is None:
            description.update('没有已发布且启用的模板，请到“模板管理”中启用。')
            self.query_one('#create-project', Button).disabled = True
            return
        record = self.project_record
        description.update(f"{record['description']}\n\n维护者：{record['maintainer']}\n\n"
                           f"环境：{'、'.join(record['environment'])}")
        widgets = []
        for key, spec in record['parameters'].items():
            label = LABELS.get(key, key) + (' *' if spec.get('required') else '')
            default = spec.get('default', '')
            value = str(default) if spec['type'] == 'string' else (json.dumps(default) if default != '' else '')
            if old_reference == new_reference:
                value = previous.get(key, value)
            widgets.append(Label(label))
            if 'enum' in spec:
                options = [(str(item), str(item) if spec['type'] == 'string' else json.dumps(item))
                           for item in spec['enum']]
                widgets.append(Select(options, value=value if value in [item[1] for item in options] else Select.BLANK,
                                      id=f'param-{key}', prompt='请选择'))
            else:
                widgets.append(Input(value, id=f'param-{key}', placeholder=spec.get('description', '')))
            self.parameter_keys.append(key)
        await container.mount(*widgets)
        directory = record['kind'] == 'directory'
        for field in ('ci', 'smoke'):
            widget = self.query_one(f'#{field}', Checkbox)
            widget.disabled = directory or self.busy
            if directory:
                widget.value = False
        self.query_one('#create-project', Button).disabled = self.busy
        self.query_one('#project-error', Static).update('')

    @on(DataTable.RowHighlighted, '#template-table')
    def highlight_template(self, event):
        self.managed_reference = str(event.row_key.value)
        self.show_template_detail()

    def show_template_detail(self):
        record = next((record for record in self.records if self.reference(record) == self.managed_reference), None)
        if record:
            lines = [self.reference(record), record['description'], f"维护者：{record['maintainer']}",
                     f"支持环境：{'、'.join(record['environment'])}", f"依赖：{'、'.join(record['dependencies']) or '无'}",
                     '变更日志：' + '；'.join(record['changelog']), f"模板目录：{record['path']}", '参数：']
            for key, spec in record['parameters'].items():
                lines.append(f"  {LABELS.get(key, key)} ({key})：{spec['type']}，"
                             f"{'必填' if spec.get('required') else '可选'}，默认值 {spec.get('default', '无')}")
            self.query_one('#template-detail', Static).update('\n'.join(lines))
        for identifier in ('enable-template', 'disable-template', 'publish-template'):
            disabled = self.busy or record is None
            if record:
                if identifier == 'publish-template':
                    disabled |= record['status'] != 'draft'
                elif identifier == 'enable-template':
                    disabled |= record['status'] != 'published' or record['enabled']
                else:
                    disabled |= not record['enabled']
            self.query_one(f'#{identifier}', Button).disabled = disabled

    def message(self, text, error=False):
        self.query_one('#management-message', Static).update(text)
        self.notify(text, severity='error' if error else 'information', timeout=5)

    def refresh_environment(self):
        report = environment.environment_status()
        lines = [f"系统：{report['system']}", f"Python：{sys.version.split()[0]}",
                 f"ROS_DISTRO：{report['distro'] or '未加载'}", f"ROS_VERSION：{report['ros_version'] or '未加载'}",
                 f"ros2：{report['ros_command'] or '未找到'}"]
        import shutil
        lines.append(f"colcon：{shutil.which('colcon') or '未找到'}")
        try:
            lines.append('PyTorch：' + importlib.metadata.version('torch'))
        except importlib.metadata.PackageNotFoundError:
            lines.append('PyTorch：未安装（不影响创建项目）')
        lines.append('\n' + ('✓ ROS 创建环境符合要求' if report['ready'] else
                              'ROS 创建环境未就绪：需 Ubuntu 24.04 + Jazzy，并 source /opt/ros/jazzy/setup.bash'))
        lines.append('创建后构建测试仍需安装模板声明的依赖，以上检查不替代实际运行验证。')
        self.query_one('#environment-report', Static).update('\n'.join(lines))

    def form_values(self):
        supplied = {}
        for key in self.parameter_keys:
            widget = self.query_one(f'#param-{key}')
            value = widget.value
            spec = self.project_record['parameters'][key]
            if value is Select.BLANK:
                value = ''
            if value == '' and not spec.get('required') and 'default' not in spec:
                continue
            supplied[key] = value
        name = supplied.pop('package_name', '')
        output = self.query_one('#output', Input).value.strip()
        request = ProjectRequest(
            self.reference(self.project_record), name, output, supplied,
            initialize_git=self.query_one('#git', Checkbox).value,
            ci=self.query_one('#ci', Checkbox).value,
            smoke_test=self.query_one('#smoke', Checkbox).value,
        )
        plan = prepare_project(request)
        return {'package_name': name, **supplied}, output, plan.project_path

    @on(Button.Pressed)
    async def button_pressed(self, event):
        identifier = event.button.id
        if identifier in {'view-logs', 'back-to-form'}:
            self.show_tab('logs-tab' if identifier == 'view-logs' else 'create-tab')
            return
        if identifier == 'cancel-task':
            await self.cancel_task()
            return
        if identifier in {'refresh-templates', 'check-environment'}:
            await self.action_refresh()
            return
        if self.busy:
            return
        try:
            if identifier == 'create-project':
                if not self.project_record:
                    raise store.TemplateError('请选择已发布且启用的模板')
                supplied, output, destination = self.form_values()
                command = [sys.executable, '-u', '-m', 'rdk_cli.main', 'project', 'create',
                           self.reference(self.project_record), '--name', supplied.pop('package_name'), '--output', output]
                for key, value in supplied.items():
                    command.extend(['--param', f'{key}={value}'])
                for field, flag in [('git', '--git'), ('ci', '--ci'), ('smoke', '--smoke-test')]:
                    if self.query_one(f'#{field}', Checkbox).value:
                        command.append(flag)
                self.last_project = destination
                self.start_job(command, '创建项目', project=True,
                               auto_exit=self.query_one('#auto-exit', Checkbox).value)
            elif identifier in {'enable-template', 'disable-template', 'publish-template'}:
                if not self.managed_reference:
                    raise store.TemplateError('请先选择模板版本')
                if identifier == 'publish-template':
                    store.publish(self.managed_reference, self.query_one('#reviewer', Input).value)
                else:
                    store.set_enabled(self.managed_reference, identifier == 'enable-template')
                self.message('模板状态已更新：' + self.managed_reference)
                await self.refresh_templates()
            elif identifier == 'create-draft':
                destination = store.create_draft(
                    self.query_one('#draft-name', Input).value, self.query_one('#draft-version', Input).value,
                    self.query_one('#draft-maintainer', Input).value, self.query_one('#draft-kind', Select).value)
                self.message(f'草稿已创建：{destination}；编辑模板文件并完成评审后发布。')
                await self.refresh_templates()
            elif identifier == 'import-template':
                source = self.query_one('#import-source', Input).value.strip()
                if not source:
                    raise store.TemplateError('请填写模板来源')
                command = [sys.executable, '-u', '-m', 'rdk_cli.main', 'template', 'install', source]
                for field, flag in [('import-registry', '--registry'), ('import-ref', '--ref'), ('import-subdir', '--subdir')]:
                    value = self.query_one(f'#{field}', Input).value.strip()
                    if value:
                        command.extend([flag, value])
                self.start_job(command, '导入模板')
        except (store.TemplateError, environment.EnvironmentCheckError, OSError) as error:
            if identifier == 'create-project':
                self.query_one('#project-error', Static).update(str(error))
                self.notify(str(error), severity='error')
            else:
                self.message(str(error), error=True)

    def set_busy(self, busy):
        if busy:
            # 先移除焦点再禁用控件，避免框架把焦点顺移到旧页面并排队触发切页。
            self.set_focus(None)
        self.busy = busy
        for selector in ('Input', 'Select', 'Checkbox', 'Button'):
            for widget in self.query(selector):
                if widget.id not in {'cancel-task', 'view-logs', 'back-to-form'}:
                    widget.disabled = busy
        self.query_one('#cancel-task', Button).disabled = not busy
        self.query_one('#running', LoadingIndicator).set_class(busy, 'visible')
        if not busy:
            self.show_template_detail()
            directory = self.project_record is None or self.project_record['kind'] == 'directory'
            self.query_one('#create-project', Button).disabled = self.project_record is None
            for field in ('ci', 'smoke'):
                self.query_one(f'#{field}', Checkbox).disabled = directory

    def start_job(self, command, title, project=False, auto_exit=False):
        self.cancel_requested = False
        self.last_result = None
        self.set_busy(True)
        self.show_tab('logs-tab')
        self.query_one('#job-status', Static).update(f'运行中 · {title}（界面可继续切换，支持取消）')
        log = self.query_one('#build-log', RichLog)
        log.clear()
        log.write(Text('$ ' + shlex.join(command), style='cyan'))
        self.job_worker = self.run_worker(self.run_command(command, title, project, auto_exit), name='任务执行')

    async def run_command(self, command, title, project, auto_exit):
        log = self.query_one('#build-log', RichLog)
        try:
            code = await self.runner.run(
                command,
                on_line=lambda line: log.write(Text.from_ansi(line)),
                cancelled=lambda: self.cancel_requested,
            )
            if self.cancel_requested:
                message = '任务已取消；已生成文件保留，请检查后重试。'
                self.last_result = 'cancelled'
            elif code:
                message = f'{title}失败（退出码 {code}）；修复日志中的问题后可返回配置页重试。'
                self.last_result = 'failed'
            else:
                message = f'{title}成功' + (f'：{self.last_project}' if project else '；请到模板管理查看草稿。')
                self.last_result = 'success'
            log.write(Text(message, style='green' if self.last_result == 'success' else 'yellow'))
            self.query_one('#job-status', Static).update(message)
            if not self.cancel_requested and code == 0 and not project:
                await self.refresh_templates()
            if project and code == 0 and not self.cancel_requested and auto_exit and not self.quit_requested:
                self.exit(message)
        except (OSError, ValueError) as error:
            self.last_result = 'failed'
            message = f'{title}失败：{error}'
            log.write(Text(message, style='red'))
            self.query_one('#job-status', Static).update(message)
        finally:
            # 即使读取日志异常，也不能遗留构建进程或 Git 子进程。
            await self.terminate_process()
            self.set_busy(False)

    @property
    def process(self):
        return self.runner.process

    async def terminate_process(self):
        await self.runner.terminate()

    async def cancel_task(self):
        if self.busy:
            self.cancel_requested = True
            self.query_one('#job-status', Static).update('正在取消并清理子进程…')
            await self.terminate_process()

    async def action_refresh(self):
        if self.busy:
            self.notify('任务运行中，请完成或取消后再刷新模板。')
            return
        await self.refresh_templates()
        self.refresh_environment()

    def show_tab(self, pane):
        # 切页时同时移动焦点，防止旧页面按钮的焦点事件重新激活旧标签。
        target = '#build-log' if pane == 'logs-tab' else '#project-form'
        self.set_focus(None)
        self.query_one('#tabs', TabbedContent).active = pane
        self.query_one(target).focus()
        self.call_after_refresh(self.query_one(target).focus)

    def action_show_logs(self):
        self.show_tab('logs-tab')

    async def action_quit(self):
        self.quit_requested = True
        if self.busy:
            await self.cancel_task()
            await self.job_worker.wait()
        self.exit('已退出 Robotics DevKit。')
