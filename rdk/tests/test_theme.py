"""配色主题：配置持久化、命令行子命令与 TUI 切换。"""

import asyncio

import pytest
from textual.widgets import Button, Footer, Select, Tab
from typer.testing import CliRunner

from rdk_cli import theme
from rdk_cli.main import app as cli
from rdk_cli.tui import DevKitApp


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.delenv(theme.ENV_VAR, raising=False)
    monkeypatch.setenv(theme.CONFIG_HOME_VAR, str(tmp_path / 'config'))
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'store'))
    theme.reset_cache()
    yield
    theme.reset_cache()


def test_default_theme_and_persisted_choice():
    assert theme.active_name() == theme.DEFAULT
    assert theme.active().label == '深海蓝'

    spec = theme.set_active('neon-night')
    assert spec.name == 'neon-night'
    assert theme.active_name() == 'neon-night'
    assert theme.config_path().is_file()


def test_unknown_theme_is_rejected_and_keeps_configuration():
    with pytest.raises(theme.ThemeError):
        theme.set_active('missing')
    assert theme.active_name() == theme.DEFAULT


def test_environment_variable_overrides_saved_theme(monkeypatch):
    theme.set_active(theme.DEFAULT)
    monkeypatch.setenv(theme.ENV_VAR, 'neon-night')
    theme.reset_cache()
    assert theme.active_name() == 'neon-night'


def test_theme_commands_list_set_and_show():
    runner = CliRunner()
    listed = runner.invoke(cli, ['theme', 'list'])
    assert listed.exit_code == 0
    for name in theme.ORDER:
        assert name in listed.output

    chosen = runner.invoke(cli, ['theme', 'set', 'neon-night'])
    assert chosen.exit_code == 0
    assert theme.active_name() == 'neon-night'

    shown = runner.invoke(cli, ['theme', 'show'])
    assert shown.exit_code == 0
    assert '当前主题：霓虹紫' in shown.output

    rejected = runner.invoke(cli, ['theme', 'set', 'missing'])
    assert rejected.exit_code == 1


def test_tui_starts_with_saved_theme():
    theme.set_active('neon-night')

    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            assert app.theme == 'neon-night'
            assert app.query_one('#theme-select', Select).value == 'neon-night'
    asyncio.run(scenario())


def test_tui_theme_switch_from_select_and_shortcut():
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            assert app.theme == theme.DEFAULT
            assert app.query_one('#theme-select', Select).value == theme.DEFAULT

            app.query_one('#theme-select', Select).value = 'neon-night'
            await pilot.pause()
            assert app.theme == 'neon-night'
            assert theme.active_name() == 'neon-night'

            await pilot.press('ctrl+t')
            await pilot.pause()
            # 两套主题循环切换：霓虹之后回到默认深蓝。
            assert app.theme == theme.DEFAULT
            assert app.query_one('#theme-select', Select).value == theme.DEFAULT
            assert theme.active_name() == theme.DEFAULT
            # 主题变量真实生效。
            assert app.screen.styles.background.hex.lower() == '#171c23'
            assert app.query_one(Footer).styles.color.hex.lower() == '#e0f5ff'
            # 激活标签与主按钮上的文字必须与背景形成对比，避免被高亮块遮住。
            active_tab = next(tab for tab in app.query(Tab) if tab.has_class('-active'))
            assert active_tab.styles.background.hex.lower() == '#202b37'
            assert active_tab.styles.color.hex.lower() == '#67d5ff'
            button = app.query_one('#create-project', Button)
            assert button.styles.background.hex.lower() == '#67d5ff'
            assert button.styles.color.hex.lower() == '#171c23'
    asyncio.run(scenario())
