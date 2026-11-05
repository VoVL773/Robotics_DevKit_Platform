"""为已安装的 CLI 配置用户级入口和终端 PATH，不安装软件或修改系统目录。"""
import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import tempfile

LAUNCHER_MARKER = '# Robotics DevKit ros-cli 启动入口'
BLOCK_START = '# >>> ros-cli PATH >>>'
BLOCK_END = '# <<< ros-cli PATH <<<'


def atomic_write(path: Path, content: str, mode: int):
    """原子替换目标文件；替换链接本身，不会写坏链接指向的安装入口。"""
    descriptor, temporary = tempfile.mkstemp(prefix='.ros-cli-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            os.fchmod(output.fileno(), mode)
            output.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def launcher_content(executable: Path) -> str:
    command = shlex.quote(str(executable))
    return (f'#!/bin/sh\n{LAUNCHER_MARKER}\n'
            f'if [ ! -x {command} ]; then\n'
            '    printf "错误：CLI 环境已移动或删除，请重新运行仓库的 setup.sh。\\n" >&2\n'
            '    exit 1\n'
            'fi\n'
            f'exec {command} "$@"\n')


def check_launcher(path: Path, executable: Path):
    """只更新本工具管理的入口，或之前手工建立的同目标软链接。"""
    if path.is_symlink():
        if path.resolve() == executable.resolve():
            return
    elif path.is_file():
        if path.read_text(encoding='utf-8').splitlines()[:2] == ['#!/bin/sh', LAUNCHER_MARKER]:
            return
    elif not path.exists():
        return
    raise ValueError(f'{path} 已有其他命令；请先检查并移走它，不会覆盖。')


def profile_content(original: str, bin_dir: Path) -> str:
    """添加或更新唯一的 PATH 区块，保留用户的其他配置。"""
    directory = shlex.quote(str(bin_dir))
    block = (f'{BLOCK_START}\n'
             'case ":$PATH:" in\n'
             f'    *:{directory}:*) ;;\n'
             f'    *) export PATH={directory}:"$PATH" ;;\n'
             'esac\n'
             f'{BLOCK_END}\n')
    pattern = re.compile(r'^' + re.escape(BLOCK_START) + r'\n.*?^' + re.escape(BLOCK_END)
                         + r'(?:\n|$)', re.MULTILINE | re.DOTALL)
    if BLOCK_START in original or BLOCK_END in original:
        if original.count(BLOCK_START) != 1 or original.count(BLOCK_END) != 1 or not pattern.search(original):
            raise ValueError('已有 ros-cli PATH 区块不完整或重复，请先检查终端配置。')
        return pattern.sub(lambda match: block, original, count=1)
    separator = '\n' if not original or original.endswith('\n') else '\n\n'
    return original + separator + block


def shell_profiles(home: Path) -> list[Path]:
    """覆盖 Bash 交互/登录终端；使用 Zsh 时尊重 ZDOTDIR。"""
    login = next((home / name for name in ('.bash_profile', '.bash_login', '.profile')
                  if (home / name).exists()), home / '.profile')
    profiles = [home / '.bashrc', login]
    zsh_home = Path(os.environ.get('ZDOTDIR') or home).expanduser()
    if Path(os.environ.get('SHELL', '')).name == 'zsh' or (zsh_home / '.zshrc').exists():
        profiles += [zsh_home / '.zshrc', zsh_home / '.zprofile']
    return profiles


def configure(venv: Path, bin_dir: Path, home: Path):
    venv, bin_dir, home = venv.expanduser().resolve(), bin_dir.expanduser().resolve(), home.expanduser().resolve()
    if ':' in str(bin_dir) or '\n' in str(bin_dir):
        raise ValueError('启动目录不能包含冒号或换行，PATH 无法正确表示这种目录。')
    if bin_dir == (venv / 'bin').resolve():
        raise ValueError('启动目录不能使用虚拟环境自身的 bin 目录。')
    executable, launcher = venv / 'bin/ros-cli', bin_dir / 'ros-cli'
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError(f'找不到可执行的 CLI：{executable}，请先安装。')
    check_launcher(launcher, executable)

    # 先检查全部配置，避免发现同名命令或损坏区块后才留下部分 PATH 修改。
    updates = {}
    for profile in shell_profiles(home):
        target = profile.resolve()
        original = target.read_text(encoding='utf-8') if target.exists() else ''
        updated = profile_content(original, bin_dir)
        if updated != original:
            updates[target] = (updated, target.exists())
    bin_dir.mkdir(parents=True, exist_ok=True)
    content = launcher_content(executable)
    if launcher.is_symlink() or not launcher.exists() or launcher.read_text(encoding='utf-8') != content:
        atomic_write(launcher, content, 0o755)
    else:
        launcher.chmod(0o755)
    for target, (updated, existed) in updates.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = stat.S_IMODE(target.stat().st_mode) if existed else 0o644
        if existed:
            backup = target.with_name(target.name + '.ros-cli.bak')
            if not backup.exists() and not backup.is_symlink():
                shutil.copy2(target, backup)
        atomic_write(target, updated, mode)
        print(f'已配置终端：{target}')
    print(f'启动入口已就绪：{launcher}')


def main():
    parser = argparse.ArgumentParser(description='配置 ros-cli 用户级启动入口')
    parser.add_argument('--venv', required=True, type=Path)
    parser.add_argument('--bin-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        configure(args.venv, args.bin_dir, Path.home())
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f'错误：{error}\n')


if __name__ == '__main__':
    main()
