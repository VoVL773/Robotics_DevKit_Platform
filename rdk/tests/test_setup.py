"""安装入口的路径转义、重复配置、冲突保护和终端配置回归。"""
import importlib.util
import os
from pathlib import Path
import subprocess

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('configure_launcher', REPO / 'rdk/scripts/configure_launcher.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def installation(tmp_path, monkeypatch):
    monkeypatch.setenv('SHELL', '/bin/bash')
    monkeypatch.delenv('ZDOTDIR', raising=False)
    home = tmp_path / 'home'
    home.mkdir()
    venv = tmp_path / "环境 '含空格'"
    (venv / 'bin').mkdir(parents=True)
    executable = venv / 'bin/ros-cli'
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\n')
    executable.chmod(0o755)
    return home, venv, home / '.local/bin'


def test_launcher_preserves_working_directory_and_argument_boundaries(installation, tmp_path):
    home, venv, bin_dir = installation
    launcher.configure(venv, bin_dir, home)
    work = tmp_path / '其他工作目录'
    work.mkdir()
    result = subprocess.run([str(bin_dir / 'ros-cli'), '--name', '含 空格', '--version'],
                            cwd=work, capture_output=True, text=True, check=True)
    assert result.stdout.splitlines() == [str(work), '--name', '含 空格', '--version']


def test_configuration_is_repeatable_and_preserves_original_profiles(installation):
    home, venv, bin_dir = installation
    profile = home / '.bashrc'
    original = '# 用户原有配置\nexport KEEP_THIS=yes\n'
    profile.write_text(original)
    profile.chmod(0o600)
    launcher.configure(venv, bin_dir, home)
    first = profile.read_text()
    launcher.configure(venv, bin_dir, home)
    assert profile.read_text() == first
    assert first.startswith(original)
    assert first.count(launcher.BLOCK_START) == 1
    assert profile.stat().st_mode & 0o777 == 0o600
    assert (home / '.bashrc.ros-cli.bak').read_text() == original
    assert not (home / '.profile.ros-cli.bak').exists()
    result = subprocess.run(['/bin/sh', '-c', '. "$1"; . "$1"; printf "%s" "$PATH"',
                             'check', str(home / '.profile')],
                            env={**os.environ, 'HOME': str(home), 'PATH': '/usr/bin:/bin'},
                            capture_output=True, text=True, check=True)
    assert result.stdout.split(':').count(str(bin_dir)) == 1


def test_existing_same_target_symlink_does_not_damage_installed_command(installation):
    home, venv, bin_dir = installation
    bin_dir.mkdir(parents=True)
    executable = venv / 'bin/ros-cli'
    original = executable.read_bytes()
    (bin_dir / 'ros-cli').symlink_to(executable)
    launcher.configure(venv, bin_dir, home)
    assert not (bin_dir / 'ros-cli').is_symlink()
    assert executable.read_bytes() == original


@pytest.mark.parametrize('kind', ['file', 'link', 'directory'])
def test_existing_unmanaged_command_is_not_overwritten(installation, kind):
    home, venv, bin_dir = installation
    bin_dir.mkdir(parents=True)
    command = bin_dir / 'ros-cli'
    if kind == 'file':
        command.write_text('用户原有命令')
    elif kind == 'link':
        command.symlink_to(home / '其他程序')
    else:
        command.mkdir()
    with pytest.raises(ValueError, match='不会覆盖'):
        launcher.configure(venv, bin_dir, home)
    assert not (home / '.bashrc').exists()
    if kind == 'file':
        assert command.read_text() == '用户原有命令'
    elif kind == 'link':
        assert command.is_symlink()
    else:
        assert command.is_dir()


def test_broken_profile_is_detected_before_writing_launcher(installation):
    home, venv, bin_dir = installation
    profile = home / '.profile'
    profile.write_text(launcher.BLOCK_START + '\n未完成的区块\n')
    with pytest.raises(ValueError, match='不完整'):
        launcher.configure(venv, bin_dir, home)
    assert not bin_dir.exists()
    assert not (home / '.bashrc').exists()


def test_login_profile_and_zsh_dotfiles_are_respected(installation, monkeypatch):
    home, venv, bin_dir = installation
    (home / '.bash_profile').write_text('# 已有登录配置\n')
    zsh_home = home / '自定义 zsh 配置'
    monkeypatch.setenv('SHELL', '/bin/zsh')
    monkeypatch.setenv('ZDOTDIR', str(zsh_home))
    launcher.configure(venv, bin_dir, home)
    assert launcher.BLOCK_START in (home / '.bash_profile').read_text()
    assert not (home / '.profile').exists()
    assert launcher.BLOCK_START in (zsh_home / '.zshrc').read_text()
    assert launcher.BLOCK_START in (zsh_home / '.zprofile').read_text()


def test_managed_entry_reports_missing_runtime(installation):
    home, venv, bin_dir = installation
    launcher.configure(venv, bin_dir, home)
    (venv / 'bin/ros-cli').unlink()
    result = subprocess.run([str(bin_dir / 'ros-cli')], capture_output=True, text=True)
    assert result.returncode == 1
    assert '重新运行仓库的 setup.sh' in result.stderr


def test_launcher_directory_cannot_overwrite_venv_console_script(installation):
    home, venv, _ = installation
    with pytest.raises(ValueError, match='虚拟环境自身'):
        launcher.configure(venv, venv / 'bin', home)


@pytest.mark.parametrize('arguments, expected_code', [(['--help'], 0), (['--venv'], 2), (['--unknown'], 2)])
def test_setup_help_and_argument_errors_do_not_install(tmp_path, arguments, expected_code):
    result = subprocess.run(['bash', str(REPO / 'setup.sh'), *arguments], cwd=tmp_path,
                            env={**os.environ, 'HOME': str(tmp_path)}, capture_output=True, text=True)
    assert result.returncode == expected_code
    assert ('用法：' if expected_code == 0 else '错误：') in result.stdout + result.stderr
    assert not (tmp_path / '.local').exists()
