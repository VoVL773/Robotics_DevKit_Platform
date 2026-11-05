"""模板生命周期、校验、导入和独立生成的回归测试。"""
import json
import hashlib
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from rdk_cli.main import app
from rdk_cli import template_store as store
from rdk_cli.version import cli_version

runner = CliRunner()


def _template_content_hashes(root, *, normalize_legacy_readme=False):
    """仅归一化已评审的发行版文案差异，其他文件仍逐字节比较。"""
    hashes = {}
    for path in root.rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        relative = path.relative_to(root).as_posix()
        if relative == 'template.json':
            continue
        content = path.read_bytes()
        if relative == 'README.md' and normalize_legacy_readme:
            # 1.0.0 文档面向 Jazzy，1.1.0 文档描述 Humble/Jazzy；不修改发布模板。
            content = content.replace(
                '在 Ubuntu 24.04 中安装 ROS 2 Jazzy 和 colcon，加载环境后，将此目录放在工作空间 src/ 下。'.encode(),
                '根据所选发行版安装对应系统与 colcon（Humble：Ubuntu 22.04；Jazzy：Ubuntu 24.04），加载环境后，将此目录放在工作空间 src/ 下。'.encode(), 1,
            ).replace(b'ROS 2 Jazzy', b'ROS 2 {{ros_distro}}', 1).replace(
                b'/opt/ros/jazzy/setup.bash', b'/opt/ros/{{ros_distro}}/setup.bash', 1)
        hashes[relative] = hashlib.sha256(content).hexdigest()
    return hashes


def _assert_template_pair(base, versioned):
    left = _template_content_hashes(base, normalize_legacy_readme=True)
    right = _template_content_hashes(versioned)
    differences = sorted(name for name in left.keys() | right.keys() if left.get(name) != right.get(name))
    assert not differences, f'模板内容漂移（含新增、删除文件）：{differences}'


@pytest.mark.parametrize('base', ['ros2-cpp', 'ros2-python', 'ros2-bringup'])
def test_versioned_template_matches_base(base):
    _assert_template_pair(store.BUILTIN_ROOT / base, store.BUILTIN_ROOT / f'{base}-1.1')


@pytest.mark.parametrize('relative, remove', [
    ('CMakeLists.txt', False), ('README.md', False), ('new-file.txt', False), ('CMakeLists.txt', True),
])
def test_template_guard_reports_changed_paths(tmp_path, relative, remove):
    base, versioned = tmp_path / 'base', tmp_path / 'versioned'
    shutil.copytree(store.BUILTIN_ROOT / 'ros2-cpp', base)
    shutil.copytree(store.BUILTIN_ROOT / 'ros2-cpp-1.1', versioned)
    target = versioned / relative
    if remove:
        target.unlink()
    else:
        target.write_bytes((target.read_bytes() if target.exists() else b'') + b'x')
    with pytest.raises(AssertionError) as caught:
        _assert_template_pair(base, versioned)
    assert relative in str(caught.value)


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'store'))


def invoke(*args, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def test_management_and_training_do_not_require_ros(monkeypatch, tmp_path):
    monkeypatch.delenv('ROS_DISTRO', raising=False)
    monkeypatch.delenv('ROS_VERSION', raising=False)
    assert invoke('template', 'list').exit_code == 0
    result = invoke('project', 'create', 'pytorch-training@1.0.0', '--name', 'training_demo', '--output', str(tmp_path))
    assert result.exit_code == 0, result.output
    project = tmp_path / 'training_demo'
    lock = json.loads((project / '.robot-cli.json').read_text())
    assert lock['version'] == '1.0.0'
    assert not (project / 'package.xml').exists()
    assert not (project / 'template.json').exists()
    for path in project.rglob('*.py'):
        compile(path.read_text(), str(path), 'exec')
    for path in project.rglob('*'):
        if path.is_file():
            assert '{{' not in path.read_text(), str(path)


def test_template_lifecycle_and_version_selection(tmp_path):
    for version in ('1.0.0', '1.2.0'):
        result = invoke('template', 'create', 'team-template', '--version', version, '--maintainer', 'Team')
        assert result.exit_code == 0, result.output
        assert invoke('template', 'enable', f'team-template@{version}').exit_code == 1
        assert invoke('template', 'publish', f'team-template@{version}', '--reviewed-by', 'Reviewer').exit_code == 0
    assert store.resolve('team-template', usable=True)['version'] == '1.2.0'
    assert invoke('template', 'disable', 'team-template@1.2.0').exit_code == 0
    assert store.resolve('team-template', usable=True)['version'] == '1.0.0'
    assert invoke('project', 'create', 'team-template@1.2.0', '--name', 'demo', '--output', str(tmp_path)).exit_code == 1
    assert invoke('project', 'create', 'team-template@1.0.0', '--name', 'demo', '--output', str(tmp_path)).exit_code == 0
    before = (tmp_path / 'demo/README.md').read_bytes()
    assert invoke('template', 'enable', 'team-template@1.2.0').exit_code == 0
    assert (tmp_path / 'demo/README.md').read_bytes() == before
    assert invoke('template', 'create', 'team-template', '--version', '1.0.0', '--maintainer', 'Team').exit_code == 1
    assert invoke('template', 'publish', 'team-template@1.0.0', '--reviewed-by', 'Another').exit_code == 1
    record = store.resolve('team-template@1.0.0')
    assert record['review']['reviewed_by'] == 'Reviewer'


@pytest.mark.parametrize('name', ['Bad-Name', '../escape', 'class', 'for', 'demo_', '123demo'])
def test_invalid_names_leave_no_output(name, tmp_path):
    output = tmp_path / 'output'
    result = invoke('project', 'create', 'pytorch-training', '--name', name, '--output', str(output))
    assert result.exit_code == 1
    assert '错误' in result.output
    assert not output.exists()


def test_reject_existing_directory(tmp_path):
    destination = tmp_path / 'demo'
    destination.mkdir()
    (destination / 'keep').write_text('original')
    result = invoke('project', 'create', 'pytorch-training', '--name', 'demo', '--output', str(tmp_path))
    assert result.exit_code == 1
    assert '已经存在' in result.output
    assert (destination / 'keep').read_text() == 'original'


@pytest.mark.parametrize('arguments, expected', [
    (['--node-name', 'bad-name'], 'node_name'),
    (['--ros-distro', 'rolling'], 'ros_distro'),
    (['--maintainer', "bad'quote"], 'maintainer'),
    (['--param', 'unknown=1'], '未知'),
    (['--param', 'node_name=a', '--param', 'node_name=b'], '不能重复'),
])
def test_parameter_errors_before_ros_check(tmp_path, arguments, expected):
    output = tmp_path / 'not_created'
    result = invoke('project', 'create', 'ros2-cpp', '--name', 'demo', '--output', str(output), *arguments)
    assert result.exit_code == 1
    assert expected in result.output
    assert not output.exists()


def test_custom_parameter_schema(tmp_path):
    destination = store.create_draft('custom', '1.0.0', 'Team', 'directory')
    manifest = store.read_json(destination / 'template.json')
    manifest['parameters']['count'] = {'type': 'integer', 'required': True, 'minimum': 1, 'maximum': 5}
    manifest['parameters']['device'] = {'type': 'string', 'default': 'cpu', 'enum': ['cpu', 'cuda']}
    store.save_json(destination / 'template.json', manifest)
    (destination / 'settings.txt').write_text('{{package_name}}: {{count}} on {{device}}')
    store.publish('custom@1.0.0', 'Reviewer')
    base = ['project', 'create', 'custom', '--name', 'demo', '--output', str(tmp_path)]
    assert invoke(*base).exit_code == 1
    assert invoke(*base, '--param', 'count=0').exit_code == 1
    assert invoke(*base, '--param', 'count=true').exit_code == 1
    assert invoke(*base, '--param', 'count=2').exit_code == 0
    assert (tmp_path / 'demo/settings.txt').read_text() == 'demo: 2 on cpu'


def test_git_and_registry_import(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    manifest = store.read_json(store.BUILTIN_ROOT / 'pytorch-training/template.json')
    manifest.update(name='team-training', version='1.2.0')
    store.save_json(source / 'template.json', manifest)
    (source / 'README.md').write_text('# {{package_name}}')
    subprocess.run(['git', 'init', str(source)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(source), '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                    'commit', '-m', 'template'], check=True, capture_output=True)
    catalog = tmp_path / 'registry.json'
    catalog.write_text(json.dumps({'templates': {'team-training@1.2.0': {
        'git': str(source), 'ref': 'HEAD', 'subdir': '.'}}}))
    result = invoke('template', 'install', 'team-training@1.2.0', '--registry', str(catalog))
    assert result.exit_code == 0, result.output
    record = store.resolve('team-training@1.2.0')
    assert record['status'] == 'draft'
    assert not record['enabled']
    assert len(record['source']['commit']) == 40
    assert invoke('template', 'install', str(source)).exit_code == 1


def test_import_rejects_symlinks_and_traversal(tmp_path):
    source = tmp_path / 'external'
    source.mkdir()
    manifest = store.read_json(store.BUILTIN_ROOT / 'pytorch-training/template.json')
    manifest['name'] = 'external'
    store.save_json(source / 'template.json', manifest)
    (source / 'escape').symlink_to('/etc/passwd')
    assert invoke('template', 'install', str(source)).exit_code == 1
    assert invoke('template', 'install', str(source), '--subdir', '../').exit_code == 1
    assert not (store.store_root() / 'external').exists()


def test_alias_and_version_info():
    assert store.resolve('ros2-cpp-package@1.0.0')['name'] == 'ros2-cpp'
    assert invoke('--version').output.strip() == f'robot-cli {cli_version()}'
    data = json.loads(invoke('template', 'info', 'ros2-cpp-template@1.0.0').output)
    for key in ('maintainer', 'dependencies', 'environment', 'changelog', 'parameters'):
        assert data[key]


def test_wizard_creates_and_exits(tmp_path):
    # 默认模板按名称排序，PyTorch 第一个；空输入使用参数默认值。
    answers = f'1\n1\nBad-Name\ntrain_demo\n\n{tmp_path}\nn\nn\nn\ny\n'
    result = runner.invoke(app, ["--wizard"], input=answers)
    assert result.exit_code == 0, result.output
    assert '参数错误' in result.output
    assert '退出 CLI' in result.output
    assert (tmp_path / 'train_demo/training/train.py').exists()


def test_wizard_cancel_and_exit():
    result = runner.invoke(app, ["--wizard"], input='invalid\n0\n')
    assert result.exit_code == 0
    assert '请输入菜单' in result.output


def test_wizard_custom_typed_defaults(tmp_path):
    destination = store.create_draft('custom-wizard', '1.0.0', 'Team', 'directory')
    manifest = store.read_json(destination / 'template.json')
    manifest['parameters'].update({
        'count': {'type': 'integer', 'default': 4, 'minimum': 1},
        'debug': {'type': 'boolean', 'default': False},
        'note': {'type': 'string'},
    })
    store.save_json(destination / 'template.json', manifest)
    store.publish('custom-wizard@1.0.0', 'Reviewer')
    records = [item for item in store.inventory() if item['status'] == 'published' and item['enabled']]
    choice = next(index for index, item in enumerate(records, 1) if item['name'] == 'custom-wizard')
    answers = f'1\n{choice}\ndemo\n\n\n\n{tmp_path}\nn\ny\n'
    result = runner.invoke(app, ["--wizard"], input=answers)
    assert result.exit_code == 0, result.output
    lock = json.loads((tmp_path / 'demo/.robot-cli.json').read_text())
    assert lock['parameters']['count'] == 4
    assert lock['parameters']['debug'] is False
    assert 'note' not in lock['parameters']


@pytest.mark.parametrize('spec', [
    {'type': []}, {'type': 'integer', 'minimum': 'bad'},
    {'type': 'string', 'pattern': '['}, {'type': 'boolean', 'default': 'false'},
])
def test_invalid_schema_reports_template_error(spec):
    manifest = store.read_json(store.BUILTIN_ROOT / 'pytorch-training/template.json')
    manifest['parameters']['broken'] = spec
    with pytest.raises(store.TemplateError):
        store.validate_manifest(manifest)
