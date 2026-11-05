"""中文帮助和解析错误覆盖真实 CLI，错误退出码仍遵循原解析器。"""
import json

import pytest
import typer
from typer.testing import CliRunner

from rdk_cli.main import app
from rdk_cli.cli_locale import ChineseTyper

runner = CliRunner()


def test_mistyped_version_has_chinese_suggestion():
    result = runner.invoke(app, ['--vision'], prog_name='ros-cli')
    assert result.exit_code == 2
    for text in ('用法：', '无法识别选项：--vision', '你可能想输入：--version', 'ros-cli --help'):
        assert text in result.output
    for text in ('Usage:', 'No such option:', 'Possible options:', 'Traceback'):
        assert text not in result.output


@pytest.mark.parametrize('args, expected', [
    (['env', 'build', '--vision'], '无法识别选项'),
    (['project', 'create'], '缺少必填参数'),
    (['template', 'create', 'demo'], '--maintainer'),
    (['project', 'create', 'ros2-cpp', '--name'], '需要提供一个值'),
    (['template', 'list', 'extra'], '存在多余参数'),
    (['not-a-command'], '未知命令'),
    (['env', 'not-a-command'], '未知命令'),
])
def test_nested_parse_errors_are_chinese(args, expected):
    result = runner.invoke(app, args, prog_name='ros-cli')
    assert result.exit_code == 2, result.output
    assert expected in result.output
    assert '错误' in result.output
    assert 'Traceback' not in result.output


@pytest.mark.parametrize('args', [
    ['--help'], ['env', '--help'], ['env', 'build', '--help'],
    ['template', '--help'], ['project', 'create', '--help'],
])
def test_help_is_chinese_at_all_command_levels(args):
    result = runner.invoke(app, args, prog_name='ros-cli')
    assert result.exit_code == 0, result.output
    assert '用法： ros-cli' in result.output
    assert '选项' in result.output
    assert '显示帮助并退出。' in result.output
    for text in ('Usage:', 'Show this message', 'Options', 'Commands', '[required]', 'default:'):
        assert text not in result.output


@pytest.mark.parametrize('group', ['env', 'project', 'template'])
def test_no_argument_group_shows_chinese_help(group):
    # 不同 Typer 版本的空命令组退出码不同，与同版本的原始框架保持一致。
    reference = typer.Typer(no_args_is_help=True)
    @reference.callback()
    def callback():
        pass
    @reference.command()
    def example():
        pass
    expected = runner.invoke(reference, []).exit_code
    result = runner.invoke(app, [group], prog_name='ros-cli')
    assert result.exit_code == expected, result.output
    assert '用法：' in result.output
    assert '命令' in result.output
    assert 'Traceback' not in result.output


def test_invalid_number_keeps_parameter_name_and_uses_chinese():
    example = ChineseTyper()
    @example.callback()
    def callback():
        pass
    @example.command()
    def count(number: int = typer.Option(..., '--number')):
        pass
    result = runner.invoke(example, ['count', '--number', 'abc'])
    assert result.exit_code == 2
    assert '--number' in result.output
    assert "'abc' 不是有效的整数" in result.output


def test_unknown_command_name_is_not_translated():
    result = runner.invoke(app, ['required'])
    assert result.exit_code == 2
    assert "未知命令：'required'" in result.output


def test_json_output_and_business_error_keep_existing_contract(monkeypatch, tmp_path):
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'templates'))
    result = runner.invoke(app, ['env', 'list', '--json'])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 4
    result = runner.invoke(app, ['template', 'info', 'not-installed'])
    assert result.exit_code == 1
    assert '找不到模板' in result.output
