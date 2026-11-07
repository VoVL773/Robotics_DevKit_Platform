"""构建 wheel 后在仓库外安装，验证资源完整性与独立生成。"""
import os
import shutil
from zipfile import ZipFile
import tarfile
from pathlib import Path
import subprocess
import sys


def test_installed_wheel_contains_all_templates(tmp_path):
    project = Path(__file__).resolve().parents[1]
    source = tmp_path / 'source'
    shutil.copytree(project, source, ignore=shutil.ignore_patterns(
        '.venv', 'build', 'dist', '__pycache__', '*.egg-info', '.pytest_cache'))
    wheels = tmp_path / 'wheels'
    template_source = tmp_path / 'template-source'
    # 模拟发布：闭源仿真目录由维护者先移出，Git 忽略不代表打包忽略。
    shutil.copytree(project.parent / 'templates', template_source, ignore=shutil.ignore_patterns(
        'build', 'dist', '__pycache__', '*.egg-info', 'robot-task-lite'))
    for package in (source, template_source):
        result = subprocess.run([sys.executable, '-m', 'pip', 'wheel', str(package), '--no-deps',
                                 '--no-build-isolation', '--wheel-dir', str(wheels)],
                                capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
    template_wheel = next(wheels.glob('robot_cli_templates-*.whl'))
    with ZipFile(template_wheel) as archive:
        assert 'rdk_templates/pytorch-training/.gitignore' in archive.namelist()
        assert 'rdk_templates/ros2-python/.rdp/skeleton/setup.py' in archive.namelist()
        assert 'rdk_templates/pytorch-training/.rdp/skeleton/configs/.gitkeep' in archive.namelist()
        assert not any('robot-task-lite' in name or name.lower().endswith('.stl')
                       or '__pycache__' in name or name.endswith('.pyc') for name in archive.namelist())
    result = subprocess.run([sys.executable, '-c',
                             'from setuptools.build_meta import build_sdist; import sys; build_sdist(sys.argv[1])',
                             str(wheels)], cwd=template_source, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    with tarfile.open(next(wheels.glob('*.tar.gz'))) as archive:
        assert not any('robot-task-lite' in name or name.lower().endswith('.stl') for name in archive.getnames())
        assert any('/.rdp/skeleton/setup.py' in name for name in archive.getnames())
    wheel = next(wheels.glob('robot_cli-*.whl'))
    with ZipFile(wheel) as archive:
        assert not any('__pycache__' in name or name.endswith('.pyc') for name in archive.namelist())
        assert not any(name.startswith('rdk_templates/') for name in archive.namelist())
        assert 'rdk_cli/project_skeleton.py' in archive.namelist()
        assert 'rdk_cli/environments/assets/ros2-humble-dev.baseline.json' in archive.namelist()
        assert 'rdk_cli/environments/assets/ros2-jazzy-dev.baseline.json' in archive.namelist()
        entrypoints = archive.read(next(name for name in archive.namelist()
                                       if name.endswith('.dist-info/entry_points.txt'))).decode()
        assert 'ros-cli = rdk_cli.main:app' in entrypoints
        assert 'robot-cli = rdk_cli.main:app' in entrypoints
    target = tmp_path / 'installed'
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--target', str(target), str(wheel), str(template_wheel)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([str(target / 'bin/ros-cli'), '--help'], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': str(target)},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'project' in result.stdout and 'template' in result.stdout and 'env' in result.stdout
    script = '''
import ast
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import rdk_cli.main as cli
from rdk_cli.project_files import render_template
from rdk_cli.project_skeleton import render_skeleton
from rdk_cli.environments.context import ASSETS
assert ASSETS.is_relative_to(Path(sys.argv[1]))
assert (ASSETS / 'Dockerfile').is_file()
import rdk_cli.tui as tui
assert Path(tui.__file__).is_relative_to(Path(sys.argv[1]))
from rdk_cli import template_store as store
assert Path(cli.__file__).is_relative_to(Path(sys.argv[1]))
assert store.BUILTIN_ROOT.is_relative_to(Path(sys.argv[1]))
assert len(store.inventory()) == 7
assert all(record['name'] != 'robot-task-lite' for record in store.inventory())
for record in store.inventory():
    values = store.parameters(record, {'package_name': 'wheel_demo'})
    values.update(template_id=record['name'], template_version=record['version'],
                  package_name_upper='WHEEL_DEMO', language=record['kind'])
    destination = Path(sys.argv[2]) / record['name']
    render_template(record, destination, values)
    assert (destination / 'README.md').is_file()
    for path in destination.rglob('*.py'):
        ast.parse(path.read_text())
for reference in ('pytorch-training',):
    record = store.resolve(reference)
    render_skeleton(record, Path(sys.argv[2]) / ('blank_' + reference), {'package_name': 'blank'})
    assert (Path(sys.argv[2]) / ('blank_' + reference) / 'README.md').is_file()
sys.argv = ['robot-cli', 'project', 'create', 'pytorch-training@1.0.0',
            '--name', 'standalone', '--output', sys.argv[2]]
cli.app()
'''
    result = subprocess.run([sys.executable, '-I', '-c', script, str(target), str(tmp_path / 'generated')],
                            cwd=tmp_path, env={**os.environ, 'ROBOT_CLI_TEMPLATE_HOME': str(tmp_path / 'store')},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / 'generated/standalone/training/train.py').is_file()
