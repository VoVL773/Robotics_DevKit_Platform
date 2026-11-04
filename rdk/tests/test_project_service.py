"""应用服务可脱离界面使用，预检无副作用，生成结果与命令入口一致。"""
import json
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from rdk_cli.main import app
from rdk_cli import template_store as store
from rdk_cli.project_service import ProjectRequest, create_project, prepare_project


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'store'))


def test_service_import_does_not_load_presentation_layer():
    result = subprocess.run([sys.executable, '-c', '''
import sys
from rdk_cli.project_service import ProjectRequest, prepare_project
assert not {'typer', 'rich', 'textual', 'rdk_cli.main', 'rdk_cli.tui'} & sys.modules.keys()
'''], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('name, parameters', [
    ('Bad-Name', {}), ('class', {}), ('demo', {'unknown': '1'}),
    ('demo', {'package_name': 'another'}),
])
def test_rejected_preflight_has_no_filesystem_side_effects(tmp_path, name, parameters):
    output = tmp_path / 'not_created'
    with pytest.raises(store.TemplateError):
        prepare_project(ProjectRequest('pytorch-training', name, str(output), parameters))
    assert not output.exists()


def test_service_and_cli_generate_identical_files(tmp_path):
    direct = tmp_path / 'direct'
    via_cli = tmp_path / 'cli'
    plan = prepare_project(ProjectRequest('pytorch-training@1.0.0', 'demo', str(direct), ci=True))
    assert not direct.exists()
    assert plan.reference == 'pytorch-training@1.0.0'
    assert create_project(plan) == direct / 'demo'
    result = CliRunner().invoke(app, ['project', 'create', plan.reference, '--name', 'demo',
                                     '--output', str(via_cli), '--ci'])
    assert result.exit_code == 0, result.output
    def contents(root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert contents(direct / 'demo') == contents(via_cli / 'demo')
    assert json.loads((direct / 'demo/.robot-cli.json').read_text())['version'] == '1.0.0'


def test_environment_errors_are_domain_errors(monkeypatch, tmp_path):
    from rdk_cli import environment
    monkeypatch.delenv('ROS_DISTRO', raising=False)
    output = tmp_path / 'not_created'
    with pytest.raises(environment.EnvironmentCheckError, match='Jazzy'):
        prepare_project(ProjectRequest('ros2-cpp', 'demo', str(output)))
    assert not output.exists()
