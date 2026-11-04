"""构建 wheel 后在仓库外安装，验证资源完整性与独立生成。"""
import os
import shutil
from zipfile import ZipFile
from pathlib import Path
import subprocess
import sys


def test_installed_wheel_contains_all_templates(tmp_path):
    project = Path(__file__).resolve().parents[1]
    source = tmp_path / 'source'
    shutil.copytree(project, source, ignore=shutil.ignore_patterns(
        '.venv', 'build', 'dist', '__pycache__', '*.egg-info', '.pytest_cache'))
    wheels = tmp_path / 'wheels'
    result = subprocess.run([sys.executable, '-m', 'pip', 'wheel', str(source), '--no-deps',
                             '--no-build-isolation', '--wheel-dir', str(wheels)],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    wheel = next(wheels.glob('robot_cli-*.whl'))
    with ZipFile(wheel) as archive:
        assert not any('__pycache__' in name or name.endswith('.pyc') for name in archive.namelist())
        assert 'rdk_templates/pytorch-training/.gitignore' in archive.namelist()
    target = tmp_path / 'installed'
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--target', str(target), str(wheel)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    script = '''
import ast
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import rdk_cli.main as cli
from rdk_cli.project_files import render_template
import rdk_cli.tui as tui
assert Path(tui.__file__).is_relative_to(Path(sys.argv[1]))
from rdk_cli import template_store as store
assert Path(cli.__file__).is_relative_to(Path(sys.argv[1]))
assert store.BUILTIN_ROOT.is_relative_to(Path(sys.argv[1]))
assert len(store.inventory()) == 4
for record in store.inventory():
    values = store.parameters(record, {'package_name': 'wheel_demo'})
    values.update(template_id=record['name'], template_version=record['version'],
                  package_name_upper='WHEEL_DEMO', language=record['kind'])
    destination = Path(sys.argv[2]) / record['name']
    render_template(record, destination, values)
    assert (destination / 'README.md').is_file()
    for path in destination.rglob('*.py'):
        ast.parse(path.read_text())
sys.argv = ['robot-cli', 'project', 'create', 'pytorch-training@1.0.0',
            '--name', 'standalone', '--output', sys.argv[2]]
cli.app()
'''
    result = subprocess.run([sys.executable, '-I', '-c', script, str(target), str(tmp_path / 'generated')],
                            cwd=tmp_path, env={**os.environ, 'ROBOT_CLI_TEMPLATE_HOME': str(tmp_path / 'store')},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / 'generated/standalone/training/train.py').is_file()
