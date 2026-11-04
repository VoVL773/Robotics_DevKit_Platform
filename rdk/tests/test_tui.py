"""通过 Textual 的无头终端真实操作控件，验证后台任务与进程清理。"""

import asyncio
import json
import os
from pathlib import Path
import sys

import pytest
from textual.widgets import Button, Checkbox, DataTable, Input, Select, TabbedContent
from typer.testing import CliRunner

from rdk_cli.main import app as cli
from rdk_cli.tui import DevKitApp
from rdk_cli import template_store as store


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'store'))


async def wait_until(pilot, predicate):
    for _ in range(150):
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError('等待界面任务超时')


def test_default_entry_starts_tui(monkeypatch):
    # CliRunner 会替换 stdout，因此分别直接验证回调所用的终端检测。
    calls = []
    monkeypatch.setattr(DevKitApp, 'run', lambda self: calls.append('started') or '工作台已退出')
    with CliRunner().isolation():
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        cli(args=[], standalone_mode=False)
    assert calls == ['started']


def test_noninteractive_default_has_clear_error():
    result = CliRunner().invoke(cli, [])
    assert result.exit_code == 1
    assert '--wizard' in result.output


def test_tui_loads_templates_switches_forms_and_keeps_input_on_refresh():
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            assert len(app.records) == 7
            assert app.project_record['name'] == 'pytorch-training'
            app.query_one('#param-package_name', Input).value = 'keep_me'
            await pilot.press('f5')
            await pilot.pause()
            assert app.query_one('#param-package_name', Input).value == 'keep_me'
            app.query_one('#project-template', Select).value = 'ros2-cpp@1.0.0'
            await pilot.pause()
            assert app.query_one('#param-node_name', Input).value == 'hello_node'
            assert app.query_one('#param-ros_distro', Select).value == 'jazzy'
            assert app.query_one('#param-package_name', Input).value == ''
            await pilot.press('ctrl+l')
            assert app.query_one('#tabs', TabbedContent).active == 'logs-tab'
    asyncio.run(scenario())


@pytest.mark.parametrize('size', [(120, 42), (80, 24)])
def test_invalid_form_then_real_creation_and_fixed_action_buttons(tmp_path, size):
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            app.query_one('#param-package_name', Input).value = 'Bad-Name'
            app.query_one('#output', Input).value = str(tmp_path / 'projects')
            app.query_one('#auto-exit', Checkbox).value = False
            assert await pilot.click('#create-project')
            await pilot.pause(0.25)
            assert not app.busy
            assert not (tmp_path / 'projects').exists()
            app.query_one('#param-package_name', Input).value = 'tui_demo'
            assert await pilot.click('#create-project')
            await pilot.pause(0.25)
            await wait_until(pilot, lambda: app.last_result is not None and not app.busy)
            assert app.last_result == 'success'
            project = tmp_path / 'projects/tui_demo'
            assert (project / 'training/train.py').exists()
            assert json.loads((project / '.robot-cli.json').read_text())['version'] == '1.0.0'
            assert app.query_one('#tabs', TabbedContent).active == 'logs-tab'
            assert not app.query_one('#create-project', Button).disabled
    asyncio.run(scenario())


def test_successful_creation_can_auto_exit(tmp_path):
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            app.query_one('#param-package_name', Input).value = 'auto_exit'
            app.query_one('#output', Input).value = str(tmp_path)
            await pilot.click('#create-project')
            await pilot.pause(0.25)
            await wait_until(pilot, lambda: app.return_value is not None)
            assert '创建项目成功' in app.return_value
            assert (tmp_path / 'auto_exit/training/train.py').exists()
    asyncio.run(scenario())


def test_template_state_changes_in_management_view():
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            app.query_one('#tabs', TabbedContent).active = 'manage-tab'
            table = app.query_one('#template-table', DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            await pilot.click('#disable-template')
            await pilot.pause(0.25)
            assert not store.resolve('pytorch-training@1.0.0')['enabled']
            assert app.project_record['name'] != 'pytorch-training'
            await pilot.click('#enable-template')
            await pilot.pause(0.25)
            assert store.resolve('pytorch-training@1.0.0')['enabled']
    asyncio.run(scenario())


def test_failed_job_keeps_interface_available():
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(100, 32)) as pilot:
            app.start_job([sys.executable, '-c', 'print("failure log"); raise SystemExit(7)'], '失败测试')
            await wait_until(pilot, lambda: app.last_result is not None and not app.busy)
            assert app.last_result == 'failed'
            assert not app.query_one('#create-project', Button).disabled
    asyncio.run(scenario())


def test_cancel_terminates_entire_process_group_and_ui_remains_responsive(tmp_path):
    pid_file = tmp_path / 'pids.json'
    script = '''
import json, os, signal, subprocess, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, '-c',
    'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'])
with open(sys.argv[1], 'w') as output:
    json.dump([os.getpid(), child.pid], output)
print('ready', flush=True)
time.sleep(60)
'''
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(100, 32)) as pilot:
            app.start_job([sys.executable, '-u', '-c', script, str(pid_file)], '取消测试')
            await wait_until(pilot, pid_file.exists)
            pids = json.loads(pid_file.read_text())
            await pilot.click('#back-to-form')
            await pilot.pause(0.25)
            assert app.query_one('#tabs', TabbedContent).active == 'create-tab'
            await pilot.press('ctrl+l')
            await pilot.click('#cancel-task')
            await pilot.pause(0.25)
            await wait_until(pilot, lambda: app.last_result == 'cancelled' and not app.busy)
            for pid in pids:
                stat = Path(f'/proc/{pid}/stat')
                assert not stat.exists() or stat.read_text().split()[2] == 'Z'
    asyncio.run(scenario())


def test_quit_during_job_creation_cleans_up():
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(100, 32)) as pilot:
            app.start_job([sys.executable, '-c', 'import time; time.sleep(60)'], '退出测试')
            await app.action_quit()
            assert app.process is None
            assert not app.busy
            assert app.return_value == '已退出 Robotics DevKit。'
    asyncio.run(scenario())


def test_new_template_and_review_publish_from_ui():
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            app.query_one('#tabs', TabbedContent).active = 'manage-tab'
            app.query_one('#draft-name', Input).value = 'team-ui'
            app.query_one('#draft-version', Input).value = '1.2.0'
            app.query_one('#draft-maintainer', Input).value = 'Robot Team'
            app.query_one('#create-draft', Button).press()
            await pilot.pause()
            record = store.resolve('team-ui@1.2.0')
            assert record['status'] == 'draft'
            assert not record['enabled']
            table = app.query_one('#template-table', DataTable)
            table.move_cursor(row=next(index for index, item in enumerate(app.records)
                                       if item['name'] == 'team-ui'))
            await pilot.pause()
            app.query_one('#reviewer', Input).value = 'Reviewer'
            app.query_one('#publish-template', Button).press()
            await pilot.pause()
            assert store.resolve('team-ui@1.2.0', usable=True)['review']['reviewed_by'] == 'Reviewer'
    asyncio.run(scenario())


def test_import_local_template_from_ui(tmp_path):
    source = tmp_path / 'external'
    source.mkdir()
    manifest = store.read_json(store.BUILTIN_ROOT / 'pytorch-training/template.json')
    manifest.update(name='external-ui', kind='directory')
    store.save_json(source / 'template.json', manifest)
    (source / 'README.md').write_text('# {{package_name}}')
    async def scenario():
        app = DevKitApp()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            app.query_one('#import-source', Input).value = str(source)
            app.query_one('#import-template', Button).press()
            await pilot.pause()
            await wait_until(pilot, lambda: app.last_result is not None and not app.busy)
            assert app.last_result == 'success'
            record = store.resolve('external-ui@1.0.0')
            assert record['status'] == 'draft'
            assert not record['enabled']
    asyncio.run(scenario())
