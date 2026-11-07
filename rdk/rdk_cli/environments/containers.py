"""容器生命周期；宿主机合格则直接使用，不自动修改 Docker/驱动配置。"""
import json
import os
from pathlib import Path
import subprocess
import time
import sys

from .context import configure, digest_bytes, image_tag, lock_id, run, run_logged, verify_context, write_json
from .doctor import diagnose
from .profiles import EnvironmentError, Profile

LABEL = 'io.robot-cli.environment'



def validate_container_name(name):
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name):
        raise EnvironmentError('容器名必须以字母或数字开头，只含字母、数字、下划线、点、短横线，最多 128 字符')


def context_path(profile: Profile, root: Path):
    return root.expanduser().resolve() / profile.name / profile.version


def require_docker():
    result = run(['docker', 'info', '--format', '{{.ServerVersion}}'], capture_output=True, timeout=15)
    return result.stdout.strip()


def build(profile: Profile, root: Path, *, force_container=False, update=False, with_torch=False):
    if not force_container and diagnose(profile).host_ready:
        return {'mode': 'host', 'profile': profile.name, 'message': '宿主机满足条件，跳过容器构建'}
    report = diagnose(profile)
    if not report.container_ready:
        failed = [f'{check.name}：{check.fix}' for check in report.checks
                  if check.scope in {'container', 'gpu'} and check.status != 'pass']
        raise EnvironmentError('容器条件未满足：\n' + '\n'.join(failed))
    context = context_path(profile, root)
    lock = configure(profile, context, update, with_torch)
    image = image_tag(profile, lock)
    require_docker()
    inspected = subprocess.run(['docker', 'image', 'inspect', image], capture_output=True, text=True)
    existing_image = json.loads(inspected.stdout)[0] if inspected.returncode == 0 else None
    if existing_image and (existing_image['Config'].get('Labels') or {}).get(LABEL + '.lock') != lock_id(lock):
        raise EnvironmentError(f'同名镜像的环境锁不符：{image}；请人工检查，不会覆盖')
    if not existing_image:
        run_logged(['docker', 'build', '--platform', 'linux/amd64', '--tag', image,
             '--label', f'{LABEL}={profile.name}', '--label', f'{LABEL}.lock={lock_id(lock)}',
             '--build-arg', f'BASE_IMAGE={lock["base_digest"]}', '--build-arg', f'ROS_DISTRO={profile.ros}',
             '--build-arg', f'WITH_TORCH={int(with_torch)}', str(context)])
    info = json.loads(run(['docker', 'image', 'inspect', image], capture_output=True).stdout)[0]
    write_json(context / 'build.json', {'image': image, 'image_id': info['Id'], 'lock': lock_id(lock),
                                       'verification': 'pending'})
    return {'mode': 'container', 'profile': profile.name, 'image': image, 'context': str(context), 'lock': lock_id(lock), 'image_id': info['Id']}



def identity_files(image, context):
    """为不同宿主机 UID/GID 提供账号解析，不改镜像，也不暴露宿主机账号文件。"""
    uid, gid = os.getuid(), os.getgid()
    target = context / 'identities' / f'{uid}-{gid}'
    target.mkdir(parents=True, exist_ok=True)
    for filename, identifier, field in [('passwd', uid, 2), ('group', gid, 2)]:
        content = run(['docker', 'run', '--rm', '--entrypoint', 'cat', image, f'/etc/{filename}'],
                      capture_output=True, timeout=30).stdout
        rows = [line.split(':') for line in content.splitlines()]
        if not any(len(row) > field and row[field] == str(identifier) for row in rows):
            if filename == 'passwd':
                content += f'rdkdev_{uid}:x:{uid}:{gid}:Robotics DevKit:/tmp/robot-cli-{uid}:/bin/bash\n'
            else:
                content += f'rdkdev_{gid}:x:{gid}:\n'
        (target / filename).write_text(content)
        (target / filename).chmod(0o644)
    return target

def initialize(profile: Profile, root: Path, workspace: Path, *, force_container=False,
               update=False, with_torch=False, container_name=None):
    if container_name:
        validate_container_name(container_name)
    workspace = workspace.expanduser().resolve()
    if not workspace.is_dir() or not os.access(workspace, os.W_OK):
        raise EnvironmentError(f'工作目录必须是当前用户可写的已有目录：{workspace}')
    result = build(profile, root, force_container=force_container, update=update, with_torch=with_torch)
    if result['mode'] == 'host':
        return result
    context = context_path(profile, root)
    lock = verify_context(context, profile, with_torch)
    name = container_name or profile.container + '-' + lock_id(lock) + '-' + digest_bytes(str(workspace).encode())[:6]
    existing = subprocess.run(['docker', 'container', 'inspect', name], capture_output=True, text=True)
    if existing.returncode == 0:
        info = json.loads(existing.stdout)[0]
        labels = info['Config'].get('Labels') or {}
        mounted = next((m.get('Source') for m in info.get('Mounts', []) if m.get('Destination') == '/workspace'), None)
        if labels.get(LABEL + '.lock') != lock_id(lock) or mounted != str(workspace):
            raise EnvironmentError(f'同名容器的锁或工作目录不同：{name}；请使用独立环境目录，或人工检查已有容器')
        run(['docker', 'start', name], capture_output=True)
    else:
        identity = identity_files(result['image'], context)
        command = ['docker', 'run', '--detach', '--name', name, '--platform', 'linux/amd64',
                   '--label', f'{LABEL}={profile.name}', '--label', f'{LABEL}.lock={lock_id(lock)}',
                   '--user', f'{os.getuid()}:{os.getgid()}', '--env', 'USER=devkit', '--env', 'LOGNAME=devkit',
                   '--env', f'HOME=/tmp/robot-cli-{os.getuid()}',
                   '--mount', f'type=bind,src={workspace},dst=/workspace',
                   '--mount', f'type=bind,src={identity / "passwd"},dst=/etc/passwd,readonly',
                   '--mount', f'type=bind,src={identity / "group"},dst=/etc/group,readonly',
                   '--workdir', '/workspace']
        if profile.gpu:
            command += ['--gpus', 'all']
        run([*command, result['image']], capture_output=True)
    result['container'] = name
    write_json(context / 'runtime.json', result)
    return result


def shell(profile: Profile, root: Path, workspace: Path, *, force_container=False, with_torch=False):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise EnvironmentError('env shell 需要交互式终端；自动化验证请使用 env verify')
    result = initialize(profile, root, workspace, force_container=force_container, with_torch=with_torch)
    if result['mode'] == 'host':
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('ROS_', 'AMENT_', 'COLCON_', 'RMW_'))
               and key not in {'PYTHONPATH', 'CMAKE_PREFIX_PATH', 'LD_LIBRARY_PATH'}}
        env['PATH'] = ':'.join(part for part in env['PATH'].split(':') if not part.startswith('/opt/ros/'))
        run(['bash', '--noprofile', '--rcfile', f'/opt/ros/{profile.ros}/setup.bash', '-i'],
            cwd=workspace, env=env)
    else:
        run(['docker', 'exec', '-it', result['container'], 'bash', '-c',
             f'mkdir -p "$HOME" && source /opt/ros/{profile.ros}/setup.bash && exec bash'])
    return result


def verify(profile: Profile, root: Path, workspace: Path, *, force_container=False, with_torch=False):
    """真实构建与测试；GPU 额外执行 CUDA 张量运算，而非仅看 nvidia-smi。"""
    result = initialize(profile, root, workspace, force_container=force_container, with_torch=with_torch)
    script = f'''set -eo pipefail
source /opt/ros/{profile.ros}/setup.bash
set -u
export PYTEST_ADDOPTS='-p no:launch_testing -p no:launch_ros'
verify_dir=$(mktemp -d /tmp/robot-cli-verify-XXXXXX)
trap 'rm -rf "$verify_dir"' EXIT
'''
    import shlex
    from rdk_cli.template_store import inventory
    # 模板目录决定验收项目；每个名称选择适配当前发行版的最新启用版本。
    candidates = {}
    for record in inventory():
        generation = record.get('generation', {})
        if record['status'] != 'published' or not record['enabled']:
            continue
        ros = record['kind'].startswith('ros2_') and profile.ros in record['ros_distro']
        training = record['kind'] == 'pytorch' and (with_torch or profile.gpu)
        if not (ros or training) or not (generation.get('smoke_engine') or generation.get('smoke_commands')):
            continue
        previous = candidates.get(record['name'])
        version = lambda item: tuple(map(int, item['version'].split('.')))
        if previous is None or version(record) > version(previous):
            candidates[record['name']] = record
    for record in candidates.values():
        name = record['name'].replace('-', '_') + '_verify'
        reference = shlex.quote(f"{record['name']}@{record['version']}")
        ros = record['kind'].startswith('ros2_')
        options = f' --ros-distro {profile.ros}' if ros else ''
        output = f'"$verify_dir/{name}/src"' if ros else '"$verify_dir"'
        script += f'robot-cli project create {reference} --name {name}{options} --output {output} --smoke-test\n'
    if profile.gpu:
        script += "python -c 'import torch; assert torch.cuda.is_available(); x=torch.ones(4, device=\"cuda\"); assert x.sum().item()==4; print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name())'\n"
    if result['mode'] == 'host':
        # 保留 CLI 虚拟环境可执行路径，避免要求用户提前安装另一份工具。
        host_script = script.replace('robot-cli project', shlex.quote(sys.executable) + ' -m rdk_cli.main project')
        run_logged(['bash', '--noprofile', '--norc', '-c', host_script], env=os.environ, timeout=600)
    else:
        run_logged(['docker', 'exec', result['container'], 'bash', '-c', script], timeout=600)
    result['verification'] = 'passed'
    result['verified_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    if result['mode'] == 'container':
        context = context_path(profile, root)
        lock = verify_context(context, profile, with_torch)
        result['lock'] = lock_id(lock)
        result['image_id'] = json.loads(run(['docker', 'image', 'inspect', result['image']], capture_output=True).stdout)[0]['Id']
        write_json(context / 'verification.json', result)
    else:
        write_json(context_path(profile, root) / 'host-verification.json', result)
    return result
