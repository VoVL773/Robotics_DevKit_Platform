"""项目创建的容器路由：主机路径映射与容器内同一 CLI 的调用。"""
import json
from pathlib import Path

from rdk_cli.template_store import save_json

from .containers import initialize, validate_container_name
from .context import run
from .profiles import EnvironmentError, get_profile


def validate_mount(plan, mount, container_name):
    validate_container_name(container_name)
    root = Path(mount).expanduser().resolve()
    if not plan.output_path.is_relative_to(root):
        raise EnvironmentError(f'项目输出位置 {plan.output_path} 必须位于挂载目录 {root} 内')
    if ',' in str(root):
        raise EnvironmentError('Docker 挂载路径暂不支持逗号，请选择其他目录')
    if root.exists() and not root.is_dir():
        raise EnvironmentError(f'挂载路径不是目录：{root}')
    return root


def create_in_container(plan, container_name, mount, root=Path('.robot-cli/environments')):
    """只有参数校验通过且用户选择容器路线后，才创建目录和容器。"""
    workspace = validate_mount(plan, mount, container_name)
    profile = get_profile(f"ros2-{plan.values['ros_distro']}-dev")
    workspace.mkdir(parents=True, exist_ok=True)
    result = initialize(profile, root, workspace, force_container=True, container_name=container_name)
    output = Path('/workspace') / plan.output_path.relative_to(workspace)
    command = ['robot-cli', 'project', 'create', plan.reference, '--name', plan.request.name,
               '--output', str(output)]
    for key, value in plan.request.parameters.items():
        command += ['--param', f'{key}={value}']
    command.append('--examples' if plan.request.include_examples else '--no-examples')
    for selected, flag in [(plan.request.initialize_git, '--git'), (plan.request.ci, '--ci'),
                           (plan.request.smoke_test, '--smoke-test')]:
        if selected:
            command.append(flag)
    # 容器内固定 host 模式，避免容器环境损坏时递归启动 Docker。
    command.append('--host-only')
    run(['docker', 'exec', result['container'], 'bash', '-c',
         f'source /opt/ros/{profile.ros}/setup.bash && exec "$@"', 'robot-cli-project', *command])
    record_environment(plan, {**result, 'mount': str(workspace), 'container_output': str(output)})
    return result


def create_in_existing(plan, container_name):
    """复用已选容器：尊重既有挂载，仅在 /tmp 安装隔离 CLI，不修改系统 Python。"""
    import os
    import shutil
    import tempfile
    from .context import ASSETS, copy_cli, digest_bytes, file_hashes
    from .discovery import discover, runtime_check
    profile = get_profile(f"ros2-{plan.values['ros_distro']}-dev")
    candidate = next((c for c in discover(profile) if c.name == container_name), None)
    if candidate is None or not candidate.compatible:
        raise EnvironmentError(f'已有容器不匹配所选环境：{container_name}；请先 env containers 查看')
    output = candidate.mapped_path(plan.output_path)
    if output is None:
        raise EnvironmentError(f'已有容器 {container_name} 没有覆盖输出目录的可写挂载；请将 --output 改为其挂载目录内路径，或新建容器')
    if not candidate.running:
        run(['docker', 'start', container_name], capture_output=True)
    run(['docker', 'exec', container_name, 'bash', '-c', runtime_check(profile)], capture_output=True)
    uid, gid = os.getuid(), os.getgid()
    with tempfile.TemporaryDirectory(prefix='robot-cli-reuse-') as temporary:
        stage = Path(temporary)
        copy_cli(stage / 'cli')
        shutil.copyfile(ASSETS / 'requirements.lock', stage / 'requirements.lock')
        fingerprint = digest_bytes(str(file_hashes(stage)).encode())[:12]
        tool = f'/tmp/robot-cli-{uid}-{fingerprint}'
        execute = ['docker', 'exec', '--user', f'{uid}:{gid}', '--env', f'HOME=/tmp/robot-cli-home-{uid}', '--env', 'USER=devkit', '--env', 'LOGNAME=devkit', container_name]
        run([*execute, 'mkdir', '-p', tool, f'/tmp/robot-cli-home-{uid}'])
        run(['docker', 'cp', str(stage) + '/.', f'{container_name}:{tool}/source'])
        script = (f'python3 -m venv --system-site-packages {tool}/venv && '
                  f'{tool}/venv/bin/pip install --no-deps -r {tool}/source/requirements.lock && '
                  f'{tool}/venv/bin/pip install --no-deps --no-build-isolation {tool}/source/cli')
        run([*execute, 'bash', '-c', script])
    command = [f'{tool}/venv/bin/robot-cli', 'project', 'create', plan.reference,
               '--name', plan.request.name, '--output', output, '--host-only']
    for key, value in plan.request.parameters.items():
        command += ['--param', f'{key}={value}']
    command.append('--examples' if plan.request.include_examples else '--no-examples')
    for selected, flag in [(plan.request.initialize_git, '--git'), (plan.request.ci, '--ci'),
                           (plan.request.smoke_test, '--smoke-test')]:
        if selected:
            command.append(flag)
    run([*execute, 'bash', '-c',
         f'source /opt/ros/{profile.ros}/setup.bash && export PATH={tool}/venv/bin:$PATH && exec "$@"',
         'robot-cli-project', *command])
    result = {'mode': 'existing-container', 'container': container_name,
              'image': candidate.image, 'output': output, 'reproducible': False}
    record_environment(plan, result)
    return result


def record_environment(plan, runtime):
    metadata_path = plan.project_path / '.robot-cli.json'
    metadata = json.loads(metadata_path.read_text())
    metadata['development_environment'] = runtime
    save_json(metadata_path, metadata)
