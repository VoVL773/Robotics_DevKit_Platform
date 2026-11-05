"""构建上下文与环境锁；只有显式更新才重新解析可变的上游仓库。"""
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

from .profiles import EnvironmentError, Profile
from .diagnose import explain_build_failure
from rdk_cli.version import cli_version

ASSETS = Path(str(files('rdk_cli').joinpath('environments/assets')))
BOOTSTRAP = '''set -euo pipefail
install -m 644 /input/ros.key /usr/share/keyrings/ros-archive-keyring.gpg
if ! grep -Rqs 'packages.ros.org/ros2/ubuntu' /etc/apt/sources.list.d; then
  . /etc/os-release
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://packages.ros.org/ros2/ubuntu ${UBUNTU_CODENAME} main" > /etc/apt/sources.list.d/robot-cli-ros2.list
fi
apt-get update >&2
apt-get -s install --no-install-recommends '''


def run(command, **kwargs):
    try:
        return subprocess.run(command, check=True, text=True, **kwargs)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or '').strip()[-2000:]
        raise EnvironmentError(f'命令失败（退出码 {error.returncode}）：{command[0]}；{detail}') from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EnvironmentError(f'无法执行 {command[0]}：{error}') from error


def run_logged(command, *, timeout=None, **kwargs):
    """实时转发构建/验收日志，并在失败后补充建议；超时仍会结束子进程。"""
    output = []
    deadline = time.monotonic() + timeout if timeout is not None else None
    try:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace',
                              start_new_session=True, **kwargs) as process:
            def forward():
                for line in process.stdout:
                    output.append(line)
                    sys.stdout.write(line)
                    sys.stdout.flush()

            reader = threading.Thread(target=forward, daemon=True)
            reader.start()
            try:
                process.wait(timeout=timeout)
                reader.join(timeout=max(0, deadline - time.monotonic()) if deadline is not None else None)
                if reader.is_alive():
                    raise subprocess.TimeoutExpired(command, timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                # bash/colcon 也可能创建子进程，超时后一起结束，避免日志管道不关闭。
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise
            finally:
                reader.join()
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command, output=''.join(output))
            return subprocess.CompletedProcess(command, process.returncode, stdout=''.join(output))
    except subprocess.CalledProcessError as error:
        detail = error.stdout or ''
        advice = explain_build_failure(detail)
        message = f'命令失败（退出码 {error.returncode}）：{command[0]}；{detail.strip()[-2000:]}'
        if advice:
            message += f'\n建议：{advice}'
        raise EnvironmentError(message) from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EnvironmentError(f'无法执行 {command[0]}：{error}') from error


def digest_bytes(content):
    return hashlib.sha256(content).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def copy_cli(destination):
    """从源码或已安装 wheel 复制可独立安装的 CLI，排除虚拟环境和工作目录。"""
    cli_root = Path(str(files('rdk_cli')))
    template_root = Path(str(files('rdk_templates')))
    shutil.copytree(cli_root, destination / 'rdk_cli', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(template_root, destination / 'templates', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (destination / 'pyproject.toml').write_text(f'''[build-system]
requires = ["setuptools==75.6.0", "wheel==0.45.1"]
build-backend = "setuptools.build_meta"
[project]
name = "robot-cli"
version = "{cli_version()}"
maintainers = [{{name = "VoVL773"}}]
requires-python = ">=3.10"
dependencies = ["typer", "rich>=13", "textual>=1.0,<2", "packaging>=24"]
[project.scripts]
robot-cli = "rdk_cli.main:app"
ros-cli = "rdk_cli.main:app"
[tool.setuptools]
packages = ["rdk_cli", "rdk_cli.commands", "rdk_cli.environments", "rdk_templates"]
[tool.setuptools.package-dir]
rdk_templates = "templates"
[tool.setuptools.package-data]
rdk_cli = ["environments/assets/*"]
rdk_templates = ["**/*", "**/.gitignore"]
''', encoding='utf-8')


def file_hashes(root):
    return {str(path.relative_to(root)): digest_bytes(path.read_bytes())
            for path in sorted(root.rglob('*')) if path.is_file()}


def lock_id(lock):
    return digest_bytes(json.dumps(lock, sort_keys=True).encode())[:12]


def image_tag(profile, lock):
    return f'{profile.image}-{lock_id(lock)}'


def verify_context(context: Path, profile: Profile, with_torch: bool):
    try:
        lock = json.loads((context / 'environment.lock.json').read_text())
    except (OSError, ValueError) as error:
        raise EnvironmentError(f'环境锁损坏：{error}；请审查后使用 --update-lock') from error
    if lock.get('profile') != profile.data() or lock.get('with_torch') != with_torch:
        raise EnvironmentError('环境配置或训练依赖选项已改变；请显式 --update-lock，并审查依赖变更')
    for name, expected in lock['files'].items():
        path = context / name
        if not path.is_file() or digest_bytes(path.read_bytes()) != expected:
            raise EnvironmentError(f'锁定文件内容已变化：{name}；请显式 --update-lock')
    current_cli = file_hashes(Path(str(files('rdk_cli'))))
    locked_cli = {name.removeprefix('cli/rdk_cli/'): digest for name, digest in lock['files'].items()
                  if name.startswith('cli/rdk_cli/')}
    if {k: v for k, v in current_cli.items() if '__pycache__' not in k and not k.endswith('.pyc')} != locked_cli:
        raise EnvironmentError('CLI 源码已改变；请使用 --update-lock 生成新的镜像摘要与依赖记录')
    return lock


def configure(profile: Profile, context: Path, update=False, with_torch=False):
    """解析上游一次并导出可审查上下文；锁定版本不可用时失败，不自动升级。"""
    if (context / 'environment.lock.json').exists() and not update:
        return verify_context(context, profile, with_torch)
    context.mkdir(parents=True, exist_ok=True)
    # 独立暂存，失败不破坏之前可构建的上下文。
    import tempfile
    with tempfile.TemporaryDirectory(prefix='robot-cli-lock-') as temporary:
        stage = Path(temporary)
        baseline_path = ASSETS / f'{profile.name}.baseline.json'
        if not update:
            if not baseline_path.is_file():
                raise EnvironmentError('此环境尚无发布的共享基线锁；请使用 env configure --update-lock 显式解析，评审生成的锁后构建')
            baseline = json.loads(baseline_path.read_text())
            if baseline['profile'] != profile.data():
                raise EnvironmentError('共享基线与环境定义不一致，请维护者发布新的环境版本')
            base = baseline['base_digest']
            shutil.copyfile(ASSETS / 'ros.key', stage / 'ros.key')
            if digest_bytes((stage / 'ros.key').read_bytes()) != baseline['key_sha256']:
                raise EnvironmentError('共享基线的 ROS 公钥摘要不一致')
            (stage / 'apt.lock').write_text(baseline['apt'])
            inspected = subprocess.run(['docker', 'image', 'inspect', base], capture_output=True)
            if inspected.returncode:
                run(['docker', 'pull', '--platform', 'linux/amd64', base])
        else:
            run(['docker', 'pull', '--platform', 'linux/amd64', profile.base])
            info = json.loads(run(['docker', 'image', 'inspect', profile.base], capture_output=True).stdout)[0]
            digests = info.get('RepoDigests', [])
            base = next((value for value in digests if '@sha256:' in value), None)
            if not base:
                raise EnvironmentError('基础镜像没有 registry digest，不能建立可复现环境锁')
            try:
                with urlopen('https://raw.githubusercontent.com/ros/rosdistro/master/ros.key', timeout=30) as response:
                    (stage / 'ros.key').write_bytes(response.read())
            except OSError as error:
                raise EnvironmentError(f'无法获取 ROS 仓库公钥：{error}') from error
            packages = ['build-essential', 'cmake', 'git', 'python3-venv', 'python3-pip', 'python3-yaml',
                        'python3-colcon-common-extensions', f'ros-{profile.ros}-ros-base',
                        f'ros-{profile.ros}-demo-nodes-cpp', f'ros-{profile.ros}-ament-cmake-gtest',
                        f'ros-{profile.ros}-ament-cmake-pytest']
            result = run(['docker', 'run', '--rm', '--platform', 'linux/amd64', '--user', '0',
                          '--mount', f'type=bind,src={stage},dst=/input,readonly',
                          '--entrypoint', 'bash', base, '-c', BOOTSTRAP + ' '.join(packages)],
                         capture_output=True, timeout=600)
            versions = re.findall(r'^Inst ([^ ]+)(?: \[[^]]+\])? \(([^ ]+)', result.stdout, re.MULTILINE)
            (stage / 'apt.lock').write_text(''.join(f'{name}={version}\n' for name, version in sorted(versions)))
        for name in ('Dockerfile', 'requirements.lock', 'CHANGELOG.md'):
            shutil.copyfile(ASSETS / name, stage / name)
        dockerfile = stage / 'Dockerfile'
        dockerfile.write_text(dockerfile.read_text().replace('ARG BASE_IMAGE\n', f'ARG BASE_IMAGE={base}\n'))
        framework = 'torch-cu126.lock' if profile.gpu else 'torch-cpu.lock'
        shutil.copyfile(ASSETS / framework, stage / 'framework.lock')
        copy_cli(stage / 'cli')
        dev = {'name': profile.name, 'build': {'dockerfile': '../Dockerfile', 'context': '..',
                'args': {'BASE_IMAGE': base, 'ROS_DISTRO': profile.ros, 'WITH_TORCH': str(int(with_torch))}},
               'workspaceMount': 'source=${localWorkspaceFolder},target=/workspace,type=bind',
               'workspaceFolder': '/workspace', 'overrideCommand': True,
               'remoteUser': 'root', 'containerEnv': {'ROS_DISTRO': profile.ros},
               'postCreateCommand': f'bash -lc "source /opt/ros/{profile.ros}/setup.bash && robot-cli --version"'}
        if profile.gpu:
            dev['runArgs'] = ['--gpus', 'all']
        write_json(stage / '.devcontainer/devcontainer.json', dev)
        lock = {'schema': 1, 'profile': profile.data(), 'base_digest': base,
                'with_torch': with_torch, 'files': file_hashes(stage)}
        write_json(stage / 'environment.lock.json', lock)
        previous = None
        if (context / 'environment.lock.json').exists():
            previous = json.loads((context / 'environment.lock.json').read_text())
            write_json(context / 'history' / f'{lock_id(previous)}.json', previous)
        for path in stage.iterdir():
            target = context / path.name
            if path.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(path, target)
            else:
                shutil.copyfile(path, target)
        history = context / 'history/changes.jsonl'
        history.parent.mkdir(exist_ok=True)
        with history.open('a') as output:
            output.write(json.dumps({'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                     'previous': lock_id(previous) if previous else None,
                                     'current': lock_id(lock), 'image': image_tag(profile, lock)}) + '\n')
        return lock
