"""只增删模板目录即可发现、生成和切换规则，不修改 CLI 注册表。"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from rdk_cli import template_store as store
from rdk_cli.environments.context import copy_cli
from rdk_cli.project_service import ProjectRequest, prepare_project, create_project, run_smoke_tests


@pytest.fixture
def author_template(monkeypatch, tmp_path):
    builtin = tmp_path / 'templates'
    source = builtin / 'contributor-demo'
    source.mkdir(parents=True)
    monkeypatch.setattr(store, 'BUILTIN_ROOT', builtin)
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'user-store'))
    manifest = {
        'name': 'contributor-demo', 'version': '1.0.0', 'description': '自定义目录模板',
        'kind': 'directory', 'status': 'published', 'maintainer': 'Contributor',
        'environment': ['Python >= 3.10'], 'dependencies': [], 'changelog': ['初版'], 'ros_distro': [],
        'aliases': ['my-demo'],
        'parameters': {'package_name': {'type': 'string', 'required': True, 'label': '工程名'},
                       'message': {'type': 'string', 'default': 'hello', 'label': '欢迎语'}},
        'generation': {'skeleton': '.rdp/skeleton', 'ci': '.rdp/ci.yml',
                       'next_steps': ['cd {{project_shell}}', 'echo {{message}}'],
                       'smoke_commands': [['{{python}}', '-c', "from pathlib import Path; Path('checked').touch()"]]},
    }
    store.save_json(source / 'template.json', manifest)
    (source / 'hello.txt').write_text('{{package_name}}: {{message}}')
    (source / '.rdp/skeleton').mkdir(parents=True)
    (source / '.rdp/skeleton/blank.txt').write_text('{{package_name}}')
    (source / '.rdp/ci.yml').write_text('name: {{package_name}}\non: [push]\n')
    return source, manifest


def test_directory_alone_controls_discovery_alias_generation_and_removal(author_template, tmp_path):
    source, manifest = author_template
    plan = prepare_project(ProjectRequest('my-demo', 'demo', str(tmp_path / 'output'), ci=True, smoke_test=True))
    assert plan.record['parameters']['message']['label'] == '欢迎语'
    project = create_project(plan)
    assert (project / 'hello.txt').read_text() == 'demo: hello'
    assert not (project / '.rdp').exists()
    assert not (project / 'checked').exists()  # 创建不隐式执行测试命令。
    assert (project / '.github/workflows/smoke.yml').read_text() == 'name: demo\non: [push]\n'
    assert plan.next_steps()[-1] == 'echo hello'
    run_smoke_tests(plan)
    assert (project / 'checked').is_file()
    blank = create_project(prepare_project(ProjectRequest('my-demo', 'blank', str(tmp_path / 'output'), include_examples=False)))
    assert (blank / 'blank.txt').read_text() == 'blank'
    assert not (blank / 'hello.txt').exists()
    manifest['generation']['next_steps'] = ['echo changed']
    store.save_json(source / 'template.json', manifest)
    assert prepare_project(ProjectRequest('my-demo', 'other', str(tmp_path))).next_steps() == ['echo changed']
    shutil.rmtree(source)
    assert store.inventory() == []
    with pytest.raises(store.TemplateError, match='找不到模板'):
        store.resolve('my-demo')


@pytest.mark.parametrize('relative', ['../outside', '/tmp/outside'])
def test_reject_control_path_escape_before_generation(author_template, tmp_path, relative):
    source, manifest = author_template
    manifest['generation']['skeleton'] = relative
    store.save_json(source / 'template.json', manifest)
    with pytest.raises(store.TemplateError, match='相对路径'):
        prepare_project(ProjectRequest('my-demo', 'demo', str(tmp_path / 'output'), include_examples=False))
    assert not (tmp_path / 'output').exists()


def test_reject_symlink_control_resource_before_generation(author_template, tmp_path):
    source, manifest = author_template
    (source / '.rdp/ci.yml').unlink()
    (source / '.rdp/ci.yml').symlink_to(source / 'hello.txt')
    with pytest.raises(store.TemplateError, match='符号链接'):
        prepare_project(ProjectRequest('my-demo', 'demo', str(tmp_path / 'output'), ci=True))
    assert not (tmp_path / 'output').exists()


def test_container_export_contains_control_assets_and_removes_stale_files(tmp_path):
    destination = tmp_path / 'cli'
    # 已有构建目录也不能残留旧私有文件。
    (destination / 'templates/old-private').mkdir(parents=True)
    (destination / 'templates/old-private/secret.STL').touch()
    copy_cli(destination)
    assert not (destination / 'templates/old-private').exists()
    assert (destination / 'templates/ros2-python/.rdp/skeleton/setup.py').is_file()
    assert (destination / 'templates/pytorch-training/.rdp/ci.yml').is_file()


def test_environment_verification_discovers_contributor_templates(author_template, monkeypatch, tmp_path):
    from rdk_cli.environments import containers
    from rdk_cli.environments.profiles import get_profile
    source, manifest = author_template
    manifest.update(kind='ros2_python', ros_distro=['jazzy'])
    manifest['generation']['smoke_engine'] = 'ros2'
    store.save_json(source / 'template.json', manifest)
    monkeypatch.setattr(containers, 'initialize', lambda *args, **kwargs: {'mode': 'host'})
    scripts = []
    monkeypatch.setattr(containers, 'run_logged', lambda command, **kwargs: scripts.append(command[-1]))
    containers.verify(get_profile('ros2-jazzy-dev'), tmp_path / 'state', tmp_path / 'workspace')
    assert 'project create contributor-demo@1.0.0' in scripts[0]
    assert 'ros2-cpp' not in scripts[0]
