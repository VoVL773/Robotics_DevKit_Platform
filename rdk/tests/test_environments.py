"""环境矩阵、只读诊断、容器路由和锁不可静默变化的回归。"""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from rdk_cli import environment, template_store as store
from rdk_cli.environments import containers, context, discovery, doctor, projects
from rdk_cli.environments.compatibility import profile_compatible
from rdk_cli.environments.profiles import EnvironmentError, get_profile
from rdk_cli.main import app
from rdk_cli.project_service import ProjectRequest, prepare_project

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'templates'))


def test_profiles_and_aliases_are_versioned():
    result = runner.invoke(app, ['env', 'list', '--json'])
    assert result.exit_code == 0
    profiles = json.loads(result.output)
    assert len(profiles) == 4
    assert get_profile('ros2-hamble-dev') == get_profile('ros2-humble-dev')
    assert get_profile('ros2-humble-dev').ubuntu == '22.04'
    assert get_profile('ros2-jazzy-dev-gpu').driver_min == '560.35.05'
    assert all(p['version'] == '1.0.0' for p in profiles)


def test_host_ready_skips_all_docker_mutation(monkeypatch, tmp_path):
    monkeypatch.setattr(containers, 'diagnose', lambda p: SimpleNamespace(host_ready=True))
    monkeypatch.setattr(containers, 'configure', lambda *a: pytest.fail('不应构建容器'))
    result = containers.initialize(get_profile('ros2-jazzy-dev'), tmp_path / 'env', tmp_path)
    assert result['mode'] == 'host'
    assert not (tmp_path / 'env').exists()


def test_reports_container_and_host_independently(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.platform, 'freedesktop_os_release', lambda: {'ID': 'ubuntu', 'VERSION_ID': '24.04'})
    monkeypatch.setattr(doctor.platform, 'python_version', lambda: '3.12.3')
    monkeypatch.setattr(doctor.Path, 'is_file', lambda p: True)
    monkeypatch.setattr(doctor.shutil, 'which', lambda p: '/usr/bin/docker')
    monkeypatch.setattr(doctor, 'probe', lambda command, **kw: (False, 'permission denied') if command[0] == 'docker' else (True, 'ROS OK'))
    report = doctor.diagnose(get_profile('ros2-jazzy-dev'), tmp_path)
    assert report.host_ready and not report.container_ready
    assert any('socket' in c.fix for c in report.checks)
    assert not doctor.diagnose(get_profile('ros2-humble-dev')).host_ready


def test_old_gpu_driver_is_not_fixed_by_docker(monkeypatch):
    monkeypatch.setattr(doctor, 'probe', lambda command, **kw:
                        (True, 'RTX 4060, 535.104.05') if command[0] == 'nvidia-smi' else (True, '{"nvidia":{}}'))
    report = doctor.diagnose(get_profile('ros2-jazzy-dev-gpu'))
    assert not report.host_ready and not report.container_ready
    assert next(c for c in report.checks if c.name == 'NVIDIA 驱动').status == 'fail'


def test_template_versions_and_compatibility_are_preserved():
    old = store.resolve('ros2-cpp@1.0.0')
    new = store.resolve('ros2-cpp@1.1.0')
    assert old['ros_distro'] == ['jazzy']
    assert new['ros_distro'] == ['humble', 'jazzy']
    assert not profile_compatible(old, get_profile('ros2-humble-dev'))[0]
    assert profile_compatible(new, get_profile('ros2-humble-dev'))[0]
    with pytest.raises(store.TemplateError):
        store.parameters(old, {'package_name': 'demo', 'ros_distro': 'humble'})


def test_humble_validation_on_ubuntu22(monkeypatch):
    monkeypatch.setattr(environment.platform, 'freedesktop_os_release', lambda: {'ID': 'ubuntu', 'VERSION_ID': '22.04'})
    monkeypatch.setenv('ROS_DISTRO', 'humble')
    monkeypatch.setenv('ROS_VERSION', '2')
    monkeypatch.setattr(environment.shutil, 'which', lambda name: '/opt/ros/humble/bin/ros2')
    environment.check_environment('humble')
    assert not environment.environment_status('jazzy')['ready']


def test_noninteractive_mismatch_offers_explicit_container_command(monkeypatch, tmp_path):
    from rdk_cli.commands import projects as commands
    def mismatch(*a):
        raise environment.EnvironmentCheckError('需要 Ubuntu 22.04 + Humble')
    monkeypatch.setattr(commands, 'check_environment', mismatch)
    result = runner.invoke(app, ['project', 'create', 'ros2-cpp', '--name', 'demo',
                                 '--ros-distro', 'humble', '--output', str(tmp_path / 'out')])
    assert result.exit_code == 1
    assert '--container-name' in result.output
    assert not (tmp_path / 'out').exists()


def test_explicit_container_route_passes_name_mount_and_distro(monkeypatch, tmp_path):
    from rdk_cli.commands import projects as commands
    calls = []
    def create(plan, name, mount, root):
        calls.append((plan, name, mount))
        return {'container': name}
    monkeypatch.setattr(commands, 'create_in_container', create)
    result = runner.invoke(app, ['project', 'create', 'ros2-cpp', '--name', 'demo', '--ros-distro', 'humble',
                                 '--output', str(tmp_path / 'src'), '--container-name', 'my-humble', '--mount', str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert calls[0][0].values['ros_distro'] == 'humble'
    assert calls[0][1:] == ('my-humble', str(tmp_path))


def test_mount_and_name_validation_happens_before_creation(tmp_path):
    plan = prepare_project(ProjectRequest('ros2-cpp', 'demo', str(tmp_path / 'out'), {'ros_distro': 'humble'}), check_host=False)
    with pytest.raises(EnvironmentError, match='必须位于'):
        projects.validate_mount(plan, tmp_path / 'other', 'valid-name')
    with pytest.raises(EnvironmentError, match='容器名'):
        projects.validate_mount(plan, tmp_path, 'bad name; echo x')
    assert not (tmp_path / 'out').exists()


def test_existing_container_maps_deepest_writable_binding(tmp_path):
    candidate = discovery.ContainerCandidate('old', 'image', False, '22.04', 'humble', True, [
        {'type': 'bind', 'source': str(tmp_path), 'target': '/ws', 'writable': True},
        {'type': 'bind', 'source': str(tmp_path / 'src'), 'target': '/source', 'writable': True},
        {'type': 'bind', 'source': '/readonly', 'target': '/ro', 'writable': False},
    ], '待启动验证')
    assert candidate.mapped_path(tmp_path / 'src/pkg') == '/source/pkg'
    assert candidate.mapped_path('/readonly/pkg') is None
    assert candidate.mapped_path(tmp_path.parent / 'escape') is None


def test_discovery_reads_stopped_container_without_start(monkeypatch, tmp_path):
    calls = []
    def probe(command, **kw):
        calls.append(command)
        if command[1] == 'ps':
            return True, 'existing'
        return True, '\n'.join(json.dumps(v) for v in ('custom:latest', False, []))
    monkeypatch.setattr(discovery, 'probe', probe)
    monkeypatch.setattr(discovery, 'read_file', lambda n, p: 'ID=ubuntu\nVERSION_ID="22.04"' if p == '/etc/os-release' else 'setup')
    candidates = discovery.discover(get_profile('ros2-humble-dev'))
    assert candidates[0].compatible
    assert not candidates[0].running
    assert all(command[1] in {'ps', 'inspect'} for command in calls)


def test_lock_rejects_tampering_and_option_drift(tmp_path):
    p = get_profile('ros2-humble-dev')
    (tmp_path / 'apt.lock').write_text('package=1.0\n')
    lock = {'profile': p.data(), 'with_torch': False, 'files': context.file_hashes(tmp_path)}
    context.write_json(tmp_path / 'environment.lock.json', lock)
    with pytest.raises(EnvironmentError, match='选项已改变'):
        context.verify_context(tmp_path, p, True)
    (tmp_path / 'apt.lock').write_text('package=2.0\n')
    with pytest.raises(EnvironmentError, match='内容已变化'):
        context.verify_context(tmp_path, p, False)


def test_exported_cli_metadata_is_valid_and_contains_environment_assets(tmp_path):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    context.copy_cli(tmp_path)
    config = tomllib.loads((tmp_path / 'pyproject.toml').read_text())
    assert 'rdk_cli.environments' in config['tool']['setuptools']['packages']
    assert (tmp_path / 'rdk_cli/environments/assets/Dockerfile').is_file()


def test_tui_mismatch_offers_container_configuration_without_spawning(monkeypatch, tmp_path):
    from rdk_cli.tui import DevKitApp
    from textual.widgets import Checkbox, Input, Select, Static
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            app.query_one('#project-template', Select).value = 'ros2-cpp'
            await pilot.pause()
            app.query_one('#param-ros_distro', Select).value = 'humble'
            app.query_one('#param-package_name', Input).value = 'demo'
            app.query_one('#output', Input).value = str(tmp_path / 'out')
            with pytest.raises(EnvironmentError, match='容器模式'):
                app.form_values()
            await pilot.pause()
            assert app.query_one('#use-container', Checkbox).value
            assert not app.busy
            assert not (tmp_path / 'out').exists()
            supplied, output, destination = app.form_values()
            assert supplied['ros_distro'] == 'humble'
            assert app.query_one('#container-name', Input).value == 'rdk-humble-demo'
    monkeypatch.setattr('rdk_cli.tui.discover', lambda p: [])
    def mismatch(*a):
        raise environment.EnvironmentCheckError('需要 Ubuntu 22.04')
    monkeypatch.setattr(environment, 'check_environment', mismatch)
    asyncio.run(scenario())


def test_default_cpu_diagnostics_never_probe_gpu(monkeypatch):
    def probe(command, **kw):
        assert command[0] != 'nvidia-smi'
        assert 'torch.cuda' not in ' '.join(command)
        return False, 'not installed'
    monkeypatch.setattr(doctor, 'probe', probe)
    report = doctor.diagnose(get_profile('ros2-jazzy-dev'))
    assert not any(c.scope == 'gpu' for c in report.checks)


def test_init_all_only_selects_cpu_profiles(monkeypatch, tmp_path):
    calls = []
    def initialize(profile, *a, **kw):
        calls.append(profile)
        return {'mode': 'host'}
    monkeypatch.setattr(containers, 'initialize', initialize)
    result = runner.invoke(app, ['env', 'init', 'all', '--workspace', str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert [p.ros for p in calls] == ['humble', 'jazzy']
    assert not any(p.gpu for p in calls)


@pytest.mark.parametrize('name', ['ros2-humble-dev', 'ros2-jazzy-dev'])
def test_first_configuration_uses_shared_immutable_baseline(monkeypatch, tmp_path, name):
    monkeypatch.setattr(context.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    monkeypatch.setattr(context, 'run', lambda *a, **kw: pytest.fail('缓存命中时不应解析网络上游'))
    profile = get_profile(name)
    generated = tmp_path / 'context'
    lock = context.configure(profile, generated)
    baseline = json.loads((context.ASSETS / f'{name}.baseline.json').read_text())
    assert lock['base_digest'] == baseline['base_digest']
    assert '@sha256:' in lock['base_digest']
    assert (generated / 'apt.lock').read_text() == baseline['apt']
    assert baseline['base_digest'] in (generated / 'Dockerfile').read_text()
    assert context.verify_context(generated, profile, False) == lock
    devconfig = generated / '.devcontainer/devcontainer.json'
    devconfig.write_text('{}')
    with pytest.raises(EnvironmentError, match='内容已变化'):
        context.verify_context(generated, profile, False)


def test_reuse_route_does_not_create_new_environment(monkeypatch, tmp_path):
    from rdk_cli.commands import projects as commands
    calls = []
    monkeypatch.setattr(commands, 'create_in_container', lambda *a: pytest.fail('不应创建新容器'))
    def reuse(plan, name):
        calls.append((plan.values['ros_distro'], name))
        return {'container': name, 'output': '/ws/src/demo'}
    monkeypatch.setattr(commands, 'create_in_existing', reuse)
    result = runner.invoke(app, ['project', 'create', 'ros2-cpp', '--name', 'demo',
                                 '--ros-distro', 'humble', '--output', str(tmp_path / 'src'),
                                 '--reuse-container', 'old-humble'])
    assert result.exit_code == 0, result.output
    assert calls == [('humble', 'old-humble')]


def test_existing_container_without_compatible_mount_is_not_started(monkeypatch, tmp_path):
    candidate = discovery.ContainerCandidate('old', 'image', False, '22.04', 'humble', True, [], 'pending')
    monkeypatch.setattr(discovery, 'discover', lambda p: [candidate])
    monkeypatch.setattr(projects, 'run', lambda *a, **kw: pytest.fail('不应启动或修改已有容器'))
    plan = prepare_project(ProjectRequest('ros2-cpp', 'demo', str(tmp_path), {'ros_distro': 'humble'}), check_host=False)
    with pytest.raises(EnvironmentError, match='可写挂载'):
        projects.create_in_existing(plan, 'old')


def test_container_identity_supports_different_host_uid_gid(monkeypatch, tmp_path):
    monkeypatch.setattr(containers.os, 'getuid', lambda: 4321)
    monkeypatch.setattr(containers.os, 'getgid', lambda: 8765)
    def read(command, **kw):
        assert command[:3] == ['docker', 'run', '--rm']
        content = 'root:x:0:0:root:/root:/bin/bash\n' if command[-1] == '/etc/passwd' else 'root:x:0:\n'
        return SimpleNamespace(stdout=content)
    monkeypatch.setattr(containers, 'run', read)
    target = containers.identity_files('locked-image', tmp_path)
    assert 'rdkdev_4321:x:4321:8765:' in (target / 'passwd').read_text()
    assert 'rdkdev_8765:x:8765:' in (target / 'group').read_text()
    assert (target / 'passwd').read_text().startswith('root:')
