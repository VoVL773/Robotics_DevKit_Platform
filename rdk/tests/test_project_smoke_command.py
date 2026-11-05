"""冒烟构建使用 PATH 中的解释器，未找到时交给 CMake 自行探测。"""
from types import SimpleNamespace

import pytest

from rdk_cli import project_service
from rdk_cli.project_service import ProjectRequest, prepare_project


@pytest.mark.parametrize('python3', ['/opt/custom/python3', None])
def test_smoke_python_path_is_discovered(monkeypatch, tmp_path, python3):
    monkeypatch.setenv('ROBOT_CLI_TEMPLATE_HOME', str(tmp_path / 'templates'))
    def which(name):
        assert name == 'python3'
        return python3
    monkeypatch.setattr(project_service.shutil, 'which', which)
    monkeypatch.setattr(project_service, '_probe_ros_python', lambda executable: (True, None))
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        assert kwargs['check']
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(project_service.subprocess, 'run', run)
    plan = prepare_project(ProjectRequest('ros2-cpp', 'demo', str(tmp_path / 'src')), check_host=False)
    project_service.run_smoke_tests(plan)
    build = commands[0]
    assert build[:5] == ['colcon', 'build', '--symlink-install', '--packages-select', 'demo']
    if python3:
        assert build[5:] == ['--cmake-args', f'-DPython3_EXECUTABLE={python3}']
    else:
        assert '--cmake-args' not in build
        assert not any(arg.startswith('-DPython3_EXECUTABLE') for arg in build)
    assert commands[1][:2] == ['bash', '-c']


def test_isolated_venv_falls_back_only_to_its_verified_base(monkeypatch):
    monkeypatch.setattr(project_service.shutil, 'which', lambda name: '/team/venv/bin/python3')
    probes = []
    def probe(executable):
        probes.append(executable)
        return (False, '/custom/python3.12') if len(probes) == 1 else (True, None)
    monkeypatch.setattr(project_service, '_probe_ros_python', probe)
    assert project_service._ros_build_python() == '/custom/python3.12'
    assert probes == ['/team/venv/bin/python3', '/custom/python3.12']


def test_incompatible_python_reports_missing_ros_before_build(monkeypatch):
    monkeypatch.setattr(project_service.shutil, 'which', lambda name: '/team/python3')
    monkeypatch.setattr(project_service, '_probe_ros_python', lambda executable: (False, None))
    with pytest.raises(project_service.EnvironmentCheckError, match='catkin_pkg'):
        project_service._ros_build_python()


def test_probe_reads_base_from_selected_interpreter(monkeypatch):
    import json
    def run(command, **kwargs):
        assert command[:2] == ['/team/venv/bin/python3', '-c']
        assert kwargs['timeout'] == 15
        return SimpleNamespace(returncode=0, stdout=json.dumps({'ready': False, 'base': '/custom/python3'}))
    monkeypatch.setattr(project_service.subprocess, 'run', run)
    assert project_service._probe_ros_python('/team/venv/bin/python3') == (False, '/custom/python3')
