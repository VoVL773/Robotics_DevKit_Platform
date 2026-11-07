"""无示例模式必须保留工程契约，且所有入口传递同一选项。"""
import ast
import json
import xml.etree.ElementTree as ET

import pytest
from typer.testing import CliRunner

from rdk_cli import template_store as store
from rdk_cli.main import app
from rdk_cli.project_service import ProjectRequest, create_project, prepare_project


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'store'))


@pytest.mark.parametrize('reference', [
    'ros2-cpp@1.0.0', 'ros2-cpp@1.1.0',
    'ros2-python@1.0.0', 'ros2-python@1.1.0',
    'ros2-bringup@1.0.0', 'ros2-bringup@1.1.0',
    'pytorch-training',
])
def test_all_builtin_skeletons_have_no_dangling_examples(monkeypatch, tmp_path, reference):
    def ros_create(command, **kwargs):
        assert '--node-name' not in command
        root = tmp_path / 'demo'
        root.mkdir()
        (root / 'package.xml').write_text('<package format="3"><name>demo</name></package>')
        (root / 'resource').mkdir()
        (root / 'resource/demo').touch()
        (root / 'setup.cfg').write_text('[develop]\nscript_dir=$base/lib/demo\n')
    monkeypatch.setattr('rdk_cli.project_service.subprocess.run', ros_create)
    plan = prepare_project(ProjectRequest(reference, 'demo', str(tmp_path), include_examples=False), check_host=False)
    root = create_project(plan)
    assert json.loads((root / '.robot-cli.json').read_text())['include_examples'] is False
    for path in root.rglob('*.py'):
        ast.parse(path.read_text())
    assert not any(p.name in {'train.py', 'hello_node.py', 'patrol.py', 'models', 'meshes'} for p in root.rglob('*'))
    assert all('ros2 launch' not in step for step in plan.next_steps())
    if plan.kind.startswith('ros2_'):
        ET.parse(root / 'package.xml')
        if plan.kind == 'ros2_python':
            assert "'console_scripts': []" in (root / 'setup.py').read_text()
        else:
            assert 'add_executable' not in (root / 'CMakeLists.txt').read_text()
        assert not (root / 'test').exists()


def test_cli_skeleton_smoke_and_ci_do_not_run_missing_training(tmp_path):
    result = CliRunner().invoke(app, ['project', 'create', 'pytorch-training', '--name', 'blank',
                                     '--output', str(tmp_path), '--no-examples', '--ci', '--smoke-test'])
    assert result.exit_code == 0, result.output
    root = tmp_path / 'blank'
    assert (root / 'training/__init__.py').exists()
    assert not (root / 'training/train.py').exists()
    workflow = (root / '.github/workflows/smoke.yml').read_text()
    assert 'import training' in workflow
    assert 'training.train' not in workflow and 'pytest -q' not in workflow
    assert json.loads((root / '.robot-cli.json').read_text())['include_examples'] is False


def test_default_still_generates_examples(tmp_path):
    root = create_project(prepare_project(ProjectRequest('pytorch-training', 'demo', str(tmp_path))))
    assert (root / 'training/train.py').exists()
    assert json.loads((root / '.robot-cli.json').read_text())['include_examples'] is True
