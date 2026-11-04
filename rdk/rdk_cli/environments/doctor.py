"""只读环境诊断：宿主机开发条件与容器运行条件分别报告。"""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass

from .profiles import Profile


def probe(command, timeout=15):
    """外部探测有超时；错误作为诊断事实返回，不中断其余检查。"""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, ((result.stdout.strip() if result.returncode == 0 else result.stderr.strip()) or result.stdout.strip())[-4000:]
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)


def version_tuple(value):
    return tuple(int(part) for part in re.findall(r'\d+', value)[:3])


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ''
    scope: str = 'host'


@dataclass
class Report:
    profile: Profile
    checks: list[Check]

    @property
    def host_ready(self):
        return all(c.status == 'pass' for c in self.checks if c.scope in {'host', 'gpu', 'compatibility'})

    @property
    def container_ready(self):
        return all(c.status == 'pass' for c in self.checks if c.scope in {'container', 'gpu', 'compatibility'})

    def data(self):
        return {'profile': self.profile.data(), 'host_ready': self.host_ready,
                'container_ready': self.container_ready,
                'checks': [asdict(check) for check in self.checks]}


def diagnose(profile: Profile, workspace: Path | None = None, template=None) -> Report:
    checks = []

    def add(name, ok, detail, fix='', scope='host', optional=False):
        checks.append(Check(name, 'pass' if ok else ('warn' if optional else 'fail'), detail, '' if ok else fix, scope))

    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}
    add('操作系统', release.get('ID') == 'ubuntu' and release.get('VERSION_ID') == profile.ubuntu,
        release.get('PRETTY_NAME', platform.system()),
        f'使用 Ubuntu {profile.ubuntu}，或 robot-cli env build {profile.name}')
    add('Python', platform.python_version().startswith(profile.python + '.'), platform.python_version(),
        f'使用 Python {profile.python}.x；ROS Python ABI 必须匹配，建议使用对应容器')
    setup = Path(f'/opt/ros/{profile.ros}/setup.bash')
    # 在干净子进程中验证绑定和工具，允许“已安装但尚未 source”的宿主机直接复用。
    clean_env = [key for key in os.environ if key.startswith(('AMENT_', 'COLCON_', 'ROS_', 'RMW_'))]
    clean_env += ['PYTHONPATH', 'CMAKE_PREFIX_PATH', 'LD_LIBRARY_PATH']
    command = ['env', *[f'--unset={key}' for key in clean_env], 'bash', '--noprofile', '--norc', '-c',
               f'source {setup} && test "$ROS_DISTRO" = {profile.ros} && '
               '/usr/bin/python3 -c "import rclpy, ament_package, yaml" && '
               'command -v ros2 && command -v colcon && command -v cmake && command -v g++ && '
               f'ros2 pkg prefix demo_nodes_cpp && ros2 pkg prefix ament_cmake_gtest']
    ok, detail = probe(command) if setup.is_file() else (False, f'未找到 {setup}')
    add('ROS / 构建工具', ok, detail,
        f'source {setup}；安装 ros-{profile.ros}-ros-base、demo-nodes-cpp、ament-cmake-gtest、colcon、cmake 和 g++')
    current = os.environ.get('ROS_DISTRO', '')
    add('当前终端 ROS', current == profile.ros, current or '未加载（env shell 会自动加载）',
        f'新终端执行 source {setup}，不要在同一终端叠加不同发行版', 'info', True)
    docker = shutil.which('docker')
    ok, detail = probe(['docker', 'info', '--format', '{{.ServerVersion}}']) if docker else (False, '未安装 Docker')
    docker_ok = ok
    add('Docker daemon', ok, ('Docker daemon 可访问' if ok else detail),
        '安装并启动 Docker；若 permission denied，请管理员配置 docker socket 权限后重新登录（本工具不会自动 sudo）', 'container')
    if workspace:
        parent = workspace.expanduser().resolve()
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        add('工作目录', parent.is_dir() and os.access(parent, os.W_OK), str(workspace),
            '选择当前用户可写的工作目录', 'host')
    add('CPU 架构', platform.machine() in {'x86_64', 'AMD64'}, platform.machine(),
        '当前锁文件面向 linux/amd64；其他架构需要独立验证与锁文件', 'host')
    if profile.gpu:
        ok, detail = probe(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'])
        drivers = [line.rsplit(',', 1)[-1].strip() for line in detail.splitlines() if ',' in line]
        supported = ok and bool(drivers) and all(version_tuple(v) >= version_tuple(profile.driver_min) for v in drivers)
        add('NVIDIA 驱动', supported, detail,
            f'安装支持 CUDA {profile.cuda} 的 NVIDIA 驱动 >= {profile.driver_min} 并重启；容器不能替代宿主机驱动', 'gpu')
        # 只检查 runtime 注册；实际 GPU 分配和 CUDA 计算必须在目标镜像中再次验证。
        runtime_ok, runtime_detail = probe(['docker', 'info', '--format', '{{range $name, $runtime := .Runtimes}}{{$name}} {{end}}']) if docker_ok else (False, 'Docker 不可访问')
        add('NVIDIA Container Toolkit', runtime_ok and 'nvidia' in runtime_detail, runtime_detail,
            '安装 nvidia-container-toolkit，运行 nvidia-ctk runtime configure --runtime=docker 后重启 Docker', 'container')
        add('CUDA / PyTorch', False, f'目标 CUDA {profile.cuda}，torch {profile.torch}；尚未执行目标镜像计算验证',
            f'robot-cli env verify {profile.name}；驱动通过不代表 CUDA 计算或仿真器兼容', 'info', True)
        ok, detail = probe([sys.executable, '-c',
            'import torch; assert torch.cuda.is_available(); '
            f'assert torch.version.cuda == "{profile.cuda}"; '
            'assert torch.ones(1, device="cuda").sum().item() == 1; '
            'print(torch.__version__, torch.version.cuda)'])
        add('宿主机 CUDA 计算', ok, detail,
            '本机安装匹配 CUDA 的 PyTorch，或使用 GPU 容器；不根据 nvidia-smi 的 CUDA 上限推断计算可用', 'host')
    if template:
        from .compatibility import profile_compatible
        matched, detail = profile_compatible(template, profile)
        add('模板兼容性', matched is True, detail, '选择匹配模板兼容矩阵的环境或联系模板维护者',
            'compatibility', matched is None)
    try:
        torch_version = importlib.metadata.version('torch')
    except importlib.metadata.PackageNotFoundError:
        torch_version = '未安装（ROS CPU 环境不要求 PyTorch）'
    add('当前 PyTorch', True, torch_version, scope='info')
    add('仿真器', False, '当前基线不包含 Isaac/Gazebo 的 GPU 兼容认证',
        '使用仿真器前按其官方版本矩阵另行验证驱动、CUDA 和图形栈', 'info', True)
    return Report(profile, checks)
