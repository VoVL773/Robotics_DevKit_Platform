"""项目应用服务：统一校验、生成计划、文件生成和冒烟测试，不导入 CLI/TUI。"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

from rdk_cli import template_store as store
from rdk_cli.environment import EnvironmentCheckError, check_environment
from rdk_cli.project_ci import workflow_for
from rdk_cli.project_files import add_runtime_dependencies, render_template
from rdk_cli.version import cli_version


@dataclass(frozen=True)
class ProjectRequest:
    template: str
    name: str
    output: str = '.'
    parameters: dict[str, str] = field(default_factory=dict)
    initialize_git: bool = False
    ci: bool = False
    smoke_test: bool = False

    @classmethod
    def from_cli(cls, template, name, output, supplied, items, **options):
        """处理可重复的 KEY=VALUE，同时拒绝命名选项与通用参数冲突。"""
        parameters = dict(supplied)
        for item in items:
            key, separator, value = item.partition('=')
            if not separator or key in parameters or key == 'package_name':
                raise store.TemplateError(f'模板参数应为 KEY=VALUE 且不能重复：{item}')
            parameters[key] = value
        return cls(template, name, output, parameters, **options)


@dataclass(frozen=True)
class ProjectPlan:
    request: ProjectRequest
    record: dict
    values: dict
    output_path: Path
    project_path: Path

    @property
    def kind(self):
        return self.record['kind']

    @property
    def reference(self):
        return f"{self.record['name']}@{self.record['version']}"

    @property
    def workspace(self):
        return self.output_path.parent if self.output_path.name == 'src' else self.output_path

    def next_steps(self):
        """返回可复制的操作命令，由 CLI、向导等展示层决定输出方式。"""
        name = self.request.name
        if self.kind.startswith('ros2_'):
            launch = 'bringup.launch.py' if self.kind == 'ros2_bringup' else 'hello.launch.py'
            return [f'cd {shlex.quote(str(self.workspace))}',
                    f'colcon build --symlink-install --packages-select {name}',
                    'source install/setup.bash', f'ros2 launch {name} {launch}']
        if self.kind == 'pytorch':
            return [f'cd {shlex.quote(str(self.project_path))}',
                    'python3 -m venv .venv && source .venv/bin/activate',
                    "python -m pip install -e '.[dev]'",
                    'python -m training.train --config configs/default.json',
                    'python -m training.evaluate --checkpoint outputs/checkpoint.pt']
        return []


def prepare_project(request: ProjectRequest, *, check_host: bool = True) -> ProjectPlan:
    """只检查并返回生成计划；参数或环境不合法时不创建任何目录。"""
    record = store.resolve(request.template, usable=True)
    if not re.fullmatch(r'[a-z](?:[a-z0-9_]*[a-z0-9])?', request.name):
        raise store.TemplateError('项目名必须以小写字母开头，只能包含小写字母、数字和下划线，且不能以下划线结尾')
    if 'package_name' in request.parameters:
        raise store.TemplateError('package_name 应通过项目名称传入，不能重复提供')
    values = store.parameters(record, {'package_name': request.name, **request.parameters})
    if record['kind'] == 'directory':
        if request.ci:
            raise store.TemplateError('通用 directory 模板需要自行提供 CI；--ci 仅支持 ROS/PyTorch')
        if request.smoke_test:
            raise store.TemplateError('通用 directory 模板需要自行执行测试')
    if not request.output.strip():
        raise store.TemplateError('请填写生成位置')
    output_path = Path(request.output).expanduser().resolve()
    project_path = output_path / request.name
    if project_path.exists() or project_path.is_symlink():
        raise store.TemplateError(f'目标路径已经存在：{project_path}')
    if check_host and record['kind'].startswith('ros2_'):
        check_environment(values.get('ros_distro', record['ros_distro'][0]))
    return ProjectPlan(request, record, values, output_path, project_path)


def create_project(plan: ProjectPlan) -> Path:
    """按照校验后的计划生成项目；外部命令输出由调用进程的终端/日志捕获。"""
    request, values = plan.request, plan.values
    if plan.kind.startswith('ros2_'):
        command = ['ros2', 'pkg', 'create', request.name,
                   '--build-type', 'ament_python' if plan.kind == 'ros2_python' else 'ament_cmake',
                   '--license', values.get('license', 'Apache-2.0'),
                   '--maintainer-name', values.get('maintainer', 'contributor'),
                   '--maintainer-email', values.get('maintainer_email', 'maintainer@example.com'),
                   '--destination-directory', str(plan.output_path)]
        if plan.kind != 'ros2_bringup':
            command += ['--dependencies', 'rclpy' if plan.kind == 'ros2_python' else 'rclcpp',
                        '--node-name', values.get('node_name', 'hello_node')]
        plan.output_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(command, check=True)
    else:
        plan.project_path.mkdir(parents=True, exist_ok=False)
    render_values = {**values, 'template_id': plan.record['name'], 'template_version': plan.record['version'],
                     'package_name_upper': request.name.upper(), 'language': plan.record.get('language', plan.kind)}
    render_template(plan.record, plan.project_path, render_values)
    if plan.kind.startswith('ros2_'):
        add_runtime_dependencies(plan.project_path, plan.kind)
    store.save_json(plan.project_path / '.robot-cli.json', {
        'template': plan.record['name'], 'version': plan.record['version'], 'parameters': values,
        'source': plan.record.get('source', 'builtin'), 'cli_version': cli_version(),
    })
    if request.ci:
        workflow = plan.project_path / '.github/workflows/smoke.yml'
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(workflow_for(plan.kind, values.get('ros_distro', 'jazzy')), encoding='utf-8')
    if request.initialize_git:
        subprocess.run(['git', 'init', str(plan.project_path)], check=True)
    return plan.project_path


def _python3_executable() -> str | None:
    """使用实际执行构建命令的 PATH，避免写死系统解释器位置。"""
    return shutil.which('python3')


def _probe_ros_python(executable: str) -> tuple[bool, str | None]:
    """检查 ROS 构建依赖，并从被检查的解释器获取其基础解释器路径。"""
    script = '''import json, sys
try:
    import catkin_pkg, ament_package, rclpy
except ImportError:
    ready = False
else:
    ready = True
print(json.dumps({'ready': ready, 'base': getattr(sys, '_base_executable', None)}))
'''
    try:
        result = subprocess.run([executable, '-c', script], capture_output=True, text=True, timeout=15)
        if result.returncode:
            return False, None
        probe = json.loads(result.stdout.strip().splitlines()[-1])
        return probe['ready'] is True, probe['base']
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError, KeyError):
        return False, None


def _ros_build_python() -> str | None:
    """优先 PATH 解释器；隔离 venv 缺少 ROS 模块时尝试它自己的基础解释器。"""
    python3 = _python3_executable()
    if not python3:
        return None
    ready, base = _probe_ros_python(python3)
    if ready:
        return python3
    if base and base != python3 and _probe_ros_python(base)[0]:
        print(f'ROS 构建：{python3} 缺少 ROS 模块，使用已验证的基础解释器 {base}。', file=sys.stderr)
        return base
    raise EnvironmentCheckError(
        f'Python 解释器 {python3} 无法导入 ROS 构建依赖（catkin_pkg、ament_package、rclpy）。'
        '请加载匹配发行版的 setup.bash，并使用包含 ROS 系统依赖的 Python 环境。')


def run_smoke_tests(plan: ProjectPlan) -> None:
    """执行已有依赖下的 ROS 构建测试或 CPU 训练评测，不负责安装依赖。"""
    if plan.kind.startswith('ros2_'):
        command = ['colcon', 'build', '--symlink-install', '--packages-select', plan.request.name]
        # 后续新增 CMake 参数时追加到同一列表，避免覆盖已有参数。
        cmake_args = []
        python3 = _ros_build_python()
        if python3:
            cmake_args.append(f'-DPython3_EXECUTABLE={python3}')
        if cmake_args:
            command += ['--cmake-args', *cmake_args]
        subprocess.run(command, cwd=plan.workspace, check=True)
        script = ('source install/setup.bash && colcon test --packages-select ' + shlex.quote(plan.request.name)
                  + ' --event-handlers console_direct+ && colcon test-result --verbose')
        subprocess.run(['bash', '-c', script], cwd=plan.workspace, check=True)
    elif plan.kind == 'pytorch':
        for command in ([sys.executable, '-m', 'pytest', '-q'],
                        [sys.executable, '-m', 'training.train'],
                        [sys.executable, '-m', 'training.evaluate']):
            subprocess.run(command, cwd=plan.project_path, check=True)
