"""真实子进程日志和错误解释的回归，不依赖 Docker 或网络。"""
import subprocess
import sys
import os
from pathlib import Path
import signal
import time

import pytest

from rdk_cli.environments.context import run_logged
from rdk_cli.environments.diagnose import explain_build_failure
from rdk_cli.environments.profiles import EnvironmentError


@pytest.mark.parametrize('output, expected', [
    ("E: Version '0.18.5-1' for 'ros-humble-rclcpp' was not found", '版本已从源上撤下'),
    ('E: Unable to locate package ros-humble-rclcpp', '发行版不匹配'),
    ("W: Failed to fetch http://packages.ros.org/ Could not resolve 'packages.ros.org'", '检查网络'),
    ('Temporary failure in name resolution', '检查网络'),
    ('ERROR: Could not install packages: Read timed out.', '检查网络'),
])
def test_known_errors_have_actionable_advice(output, expected):
    assert expected in explain_build_failure(output)


def test_unknown_error_is_not_rewritten():
    assert explain_build_failure('CMake Error: project configuration failed') is None


def test_failed_process_preserves_stdout_stderr_and_adds_advice(capsys):
    script = ('import sys; print("构建开始", flush=True); '
              'print("E: Unable to locate package missing-package", file=sys.stderr); sys.exit(7)')
    with pytest.raises(EnvironmentError) as caught:
        run_logged([sys.executable, '-c', script], timeout=10)
    output = capsys.readouterr().out
    assert '构建开始' in output
    assert 'Unable to locate package missing-package' in output
    assert '退出码 7' in str(caught.value)
    assert 'Unable to locate package missing-package' in str(caught.value)
    assert '发行版不匹配' in str(caught.value)
    assert isinstance(caught.value.__cause__, subprocess.CalledProcessError)


def test_unknown_failed_process_keeps_original_error(capsys):
    with pytest.raises(EnvironmentError, match='unknown failure') as caught:
        run_logged([sys.executable, '-c', 'import sys; print("unknown failure"); sys.exit(3)'])
    assert '建议：' not in str(caught.value)
    assert 'unknown failure' in capsys.readouterr().out


def test_successful_process_forwards_output(capsys):
    result = run_logged([sys.executable, '-c', 'print("验收成功")'], timeout=10)
    assert result.returncode == 0
    assert result.stdout == '验收成功\n'
    assert capsys.readouterr().out == '验收成功\n'


def test_non_utf8_log_does_not_break_forwarding(capsys):
    result = run_logged([sys.executable, '-c', 'import sys; sys.stdout.buffer.write(bytes([255, 10]))'])
    assert result.returncode == 0
    assert capsys.readouterr().out == '\ufffd\n'


def test_progress_and_partial_utf8_logs_are_forwarded_without_rewriting(capsys):
    script = ('import sys, time; '
              'sys.stdout.buffer.write(b"progress\\r"); sys.stdout.buffer.flush(); '
              'sys.stdout.buffer.write(bytes([0xe4])); sys.stdout.buffer.flush(); time.sleep(0.05); '
              'sys.stdout.buffer.write(bytes([0xb8, 0xad])); sys.stdout.buffer.flush()')
    result = run_logged([sys.executable, '-c', script], timeout=5)
    assert result.stdout == 'progress\r中'
    assert capsys.readouterr().out == result.stdout


def test_output_without_newline_is_forwarded_before_process_exits(monkeypatch, tmp_path):
    from rdk_cli.environments import context
    acknowledgement = tmp_path / 'log-received'
    script = '''
import pathlib, sys, time
print('ready', end='', flush=True)
while not pathlib.Path(sys.argv[1]).exists():
    time.sleep(0.01)
print(' done', flush=True)
'''

    class LogSink:
        def write(self, text):
            if 'ready' in text:
                acknowledgement.touch()

        def flush(self):
            pass

    with monkeypatch.context() as patch:
        patch.setattr(context.sys, 'stdout', LogSink())
        result = run_logged([sys.executable, '-c', script, str(acknowledgement)], timeout=2)
    assert result.stdout == 'ready done\n'


@pytest.mark.parametrize('stage', ['write', 'flush'])
def test_log_forwarding_failure_is_reported_and_process_is_stopped(monkeypatch, tmp_path, stage):
    from rdk_cli.environments import context
    pid_file = tmp_path / 'pid'
    script = ('import os, pathlib, sys, time; '
              'pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); '
              'print("original diagnostic", flush=True); time.sleep(30)')

    class BrokenLog:
        def write(self, text):
            if stage == 'write':
                raise OSError('log output failed')

        def flush(self):
            if stage == 'flush':
                raise OSError('log output failed')

    with monkeypatch.context() as patch:
        patch.setattr(context.sys, 'stdout', BrokenLog())
        with pytest.raises(EnvironmentError, match='log output failed') as caught:
            run_logged([sys.executable, '-c', script, str(pid_file)], timeout=2)
    assert isinstance(caught.value.__cause__, OSError)
    assert 'original diagnostic' in str(caught.value)
    assert not Path(f'/proc/{pid_file.read_text()}').exists()


def test_timeout_returns_even_if_detached_child_holds_log_pipe(tmp_path):
    pid_file = tmp_path / 'detached-pid'
    script = ('import pathlib, subprocess, sys; '
              'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], '
              'start_new_session=True); pathlib.Path(sys.argv[1]).write_text(str(child.pid))')
    started = time.monotonic()
    try:
        with pytest.raises(EnvironmentError) as caught:
            run_logged([sys.executable, '-c', script, str(pid_file)], timeout=0.5)
        assert isinstance(caught.value.__cause__, subprocess.TimeoutExpired)
        assert time.monotonic() - started < 3
    finally:
        # 脱离进程组的测试子进程由测试负责清理。
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_timeout_ends_process():
    with pytest.raises(EnvironmentError, match='无法执行') as caught:
        run_logged([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=0.1)
    assert isinstance(caught.value.__cause__, subprocess.TimeoutExpired)


def test_timeout_also_ends_child_holding_log_pipe():
    script = ('import subprocess, sys; '
              'subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])')
    with pytest.raises(EnvironmentError) as caught:
        run_logged([sys.executable, '-c', script], timeout=0.3)
    assert isinstance(caught.value.__cause__, subprocess.TimeoutExpired)


@pytest.mark.parametrize('mode', ['host', 'container'])
def test_verify_routes_failure_through_diagnostics(monkeypatch, tmp_path, capsys, mode):
    from rdk_cli.environments import containers, context
    from rdk_cli.environments.profiles import get_profile
    monkeypatch.setattr(containers, 'initialize', lambda *a, **kw: {'mode': mode, 'container': 'test'})
    original_popen = subprocess.Popen
    def popen(command, **kwargs):
        if mode == 'host':
            assert command[:4] == ['bash', '--noprofile', '--norc', '-c']
        else:
            assert command[:4] == ['docker', 'exec', 'test', 'bash']
        return original_popen([sys.executable, '-c',
                               'import sys; print("Could not resolve packages.ros.org"); sys.exit(1)'], **kwargs)
    monkeypatch.setattr(context.subprocess, 'Popen', popen)
    with pytest.raises(EnvironmentError, match='检查网络'):
        containers.verify(get_profile('ros2-jazzy-dev'), tmp_path / 'environments', tmp_path)
    assert 'Could not resolve packages.ros.org' in capsys.readouterr().out
    assert not (tmp_path / 'environments').exists()


def test_build_routes_failure_through_diagnostics(monkeypatch, tmp_path, capsys):
    from types import SimpleNamespace
    from rdk_cli.environments import containers, context
    from rdk_cli.environments.profiles import get_profile
    monkeypatch.setattr(containers, 'diagnose', lambda p: SimpleNamespace(host_ready=False, container_ready=True))
    monkeypatch.setattr(containers, 'configure', lambda *a: {'base_digest': 'image@sha256:test'})
    monkeypatch.setattr(containers, 'require_docker', lambda: None)
    monkeypatch.setattr(containers.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=1))
    original_popen = subprocess.Popen
    def popen(command, **kwargs):
        assert command[:2] == ['docker', 'build']
        return original_popen([sys.executable, '-c',
                               'import sys; print("Unable to locate package missing"); sys.exit(1)'], **kwargs)
    monkeypatch.setattr(context.subprocess, 'Popen', popen)
    with pytest.raises(EnvironmentError, match='发行版不匹配'):
        containers.build(get_profile('ros2-jazzy-dev'), tmp_path, force_container=True)
    assert 'Unable to locate package missing' in capsys.readouterr().out
