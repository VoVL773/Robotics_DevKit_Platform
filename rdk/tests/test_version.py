"""版本来自安装元数据，界面和导出的记录必须一致。"""
import json
from importlib import metadata

from typer.testing import CliRunner

from rdk_cli.environments.context import copy_cli
from rdk_cli.main import app
from rdk_cli.version import cli_version

runner = CliRunner()


def test_installed_version_is_used_in_cli_project_and_export(monkeypatch, tmp_path):
    def version(name):
        assert name == 'robot-cli'
        return '9.9.9'
    monkeypatch.setattr(metadata, 'version', version)
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'templates'))
    result = runner.invoke(app, ['--version'])
    assert result.exit_code == 0
    assert result.output.strip() == 'robot-cli 9.9.9'
    result = runner.invoke(app, ['project', 'create', 'pytorch-training', '--name', 'demo',
                                  '--output', str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / 'demo/.robot-cli.json').read_text())['cli_version'] == '9.9.9'
    copy_cli(tmp_path / 'export')
    assert 'version = "9.9.9"' in (tmp_path / 'export/pyproject.toml').read_text()


def test_missing_metadata_does_not_break_version(monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)
    monkeypatch.setattr(metadata, 'version', missing)
    result = runner.invoke(app, ['--version'])
    assert result.exit_code == 0
    assert result.output.strip() == 'robot-cli 0.0.0+unknown'
    assert cli_version() == '0.0.0+unknown'


def test_environment_title_uses_profile_and_cli_versions(monkeypatch):
    from dataclasses import replace
    from rdk_cli.commands import environments
    from rdk_cli.environments.profiles import get_profile
    monkeypatch.setattr(metadata, 'version', lambda name: '9.9.9')
    monkeypatch.setattr(environments, 'PROFILES', {
        'test': replace(get_profile('ros2-jazzy-dev'), version='2.3.4'),
    })
    result = runner.invoke(app, ['env', 'list'])
    assert result.exit_code == 0
    assert '环境 2.3.4 / CLI 9.9.9' in result.output
