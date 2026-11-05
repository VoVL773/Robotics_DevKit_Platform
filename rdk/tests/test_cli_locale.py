"""中文帮助与原生框架错误并存，验证退出码、异常类型和原始文本。"""
import json

import pytest
import typer
from typer.testing import CliRunner

from rdk_cli.main import app
from rdk_cli.cli_locale import ChineseTyper

runner = CliRunner()


def test_mistyped_version_keeps_original_framework_error():
    result = runner.invoke(app, ['--vision'], prog_name='ros-cli')
    assert result.exit_code == 2
    for text in ('Usage:', 'No such option: --vision', '--version', 'ros-cli --help'):
        assert text in result.output
    for text in ('无法识别选项', '你可能想输入', 'Traceback'):
        assert text not in result.output


@pytest.mark.parametrize('args, expected', [
    (['env', 'build', '--vision'], 'No such option'),
    (['project', 'create'], 'Missing argument'),
    (['template', 'create', 'demo'], '--maintainer'),
    (['project', 'create', 'ros2-cpp', '--name'], 'requires an argument'),
    (['template', 'list', 'extra'], 'unexpected extra argument'),
    (['not-a-command'], 'No such command'),
    (['env', 'not-a-command'], 'No such command'),
])
def test_nested_parse_errors_remain_original(args, expected):
    result = runner.invoke(app, args, prog_name='ros-cli')
    assert result.exit_code == 2, result.output
    assert expected in result.output
    assert 'Error:' in result.output
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
    for text in ('Usage:', 'Show this message', 'Options', 'Commands'):
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


def test_invalid_number_keeps_original_error():
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
    assert "'abc' is not a valid" in result.output


def test_unknown_command_name_is_not_translated():
    result = runner.invoke(app, ['required'])
    assert result.exit_code == 2
    assert "No such command 'required'" in result.output


def test_json_output_and_business_error_keep_existing_contract(monkeypatch, tmp_path):
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'templates'))
    result = runner.invoke(app, ['env', 'list', '--json'])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 4
    result = runner.invoke(app, ['template', 'info', 'not-installed'])
    assert result.exit_code == 1
    assert '找不到模板' in result.output


@pytest.mark.parametrize('args', [
    ['--unknown'], ['count'], ['count', '--number', 'abc'],
    ['count', '--number'], ['count', '--number', '1', 'extra'], ['unknown'],
])
def test_parse_error_matches_native_framework_including_exception_type(args):
    def make_app(factory):
        example = factory(rich_markup_mode=None)
        @example.callback()
        def callback():
            pass
        @example.command()
        def count(number: int = typer.Option(..., '--number')):
            pass
        return example

    native = make_app(typer.Typer)
    localized = make_app(ChineseTyper)
    expected = runner.invoke(native, args, prog_name='test-cli')
    actual = runner.invoke(localized, args, prog_name='test-cli')
    assert actual.exit_code == expected.exit_code
    assert actual.output == expected.output
    expected_exception = runner.invoke(native, args, standalone_mode=False).exception
    actual_exception = runner.invoke(localized, args, standalone_mode=False).exception
    assert type(actual_exception) is type(expected_exception)
    assert str(actual_exception) == str(expected_exception)


def test_help_does_not_translate_user_text_or_default_values():
    example = ChineseTyper()
    @example.command()
    def count(value: str = typer.Option("No such command 'required'.", help='Show this message and exit.')):
        pass
    result = runner.invoke(example, ['--help'])
    assert result.exit_code == 0
    unwrapped = ' '.join(result.output.replace('│', '').split())
    assert "No such command 'required'." in unwrapped
    assert 'Show this message and exit.' in result.output
