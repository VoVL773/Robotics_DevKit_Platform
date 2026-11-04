"""只读枚举已有容器；不凭镜像名判断 ROS，不自动启动业务容器。"""
from dataclasses import asdict, dataclass
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

from .doctor import probe
from .profiles import Profile


@dataclass
class ContainerCandidate:
    name: str
    image: str
    running: bool
    ubuntu: str
    ros: str
    compatible: bool
    mounts: list[dict]
    detail: str

    def data(self):
        return asdict(self)

    def mapped_path(self, host_path):
        host_path = Path(host_path).expanduser().resolve()
        mappings = [m for m in self.mounts if m['type'] == 'bind' and m['writable']
                    and host_path.is_relative_to(Path(m['source']))]
        if not mappings:
            return None
        match = max(mappings, key=lambda m: len(m['source']))
        return str(PurePosixPath(match['target']) / host_path.relative_to(match['source']))


def read_file(container, path):
    """docker cp 支持停止的容器，不改变其状态或文件。"""
    try:
        result = subprocess.run(['docker', 'cp', '-L', f'{container}:{path}', '-'], capture_output=True, timeout=10)
        if result.returncode:
            return ''
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode='r:*') as archive:
            member = next((m for m in archive if m.isfile()), None)
            if member:
                return archive.extractfile(member).read(128 * 1024).decode(errors='replace')
    except (OSError, subprocess.TimeoutExpired, tarfile.TarError):
        pass
    return ''


def runtime_check(profile: Profile):
    return (f'source /opt/ros/{profile.ros}/setup.bash && '
            f'test "$ROS_DISTRO" = {profile.ros} && '
            'python3 -c "import rclpy, ament_package, yaml, venv, ensurepip" && '
            'command -v ros2 && command -v colcon && command -v cmake && command -v g++')


def discover(profile: Profile) -> list[ContainerCandidate]:
    ok, output = probe(['docker', 'ps', '-a', '--format', '{{.Names}}'])
    if not ok:
        return []
    candidates = []
    for name in output.splitlines():
        ok, detail = probe(['docker', 'inspect', '--format',
            '{{json .Config.Image}}\n{{json .State.Running}}\n{{json .Mounts}}', name])
        if not ok:
            continue
        try:
            image, running, mounts = map(json.loads, detail.splitlines())
        except (ValueError, TypeError):
            continue
        release = dict(line.split('=', 1) for line in read_file(name, '/etc/os-release').splitlines() if '=' in line)
        os_id = release.get('ID', '').strip('"')
        ubuntu = release.get('VERSION_ID', '').strip('"')
        setup = read_file(name, f'/opt/ros/{profile.ros}/setup.bash')
        match = os_id == 'ubuntu' and ubuntu == profile.ubuntu and bool(setup)
        reason = '停止状态：已检查系统和 ROS 文件，启动后还需验证构建工具'
        if running and match:
            match, reason = probe(['docker', 'exec', name, 'bash', '-c', runtime_check(profile)])
        elif not match:
            reason = f'需要 Ubuntu {profile.ubuntu} + {profile.ros}；当前 Ubuntu {ubuntu or "未知"}，对应 ROS 文件{"存在" if setup else "不存在"}'
        candidates.append(ContainerCandidate(name, image, running, ubuntu,
            profile.ros if setup else '', match,
            [{'type': m['Type'], 'source': m['Source'], 'target': m['Destination'],
              'writable': m.get('RW', False)} for m in mounts], reason))
    return candidates
