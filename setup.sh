#!/usr/bin/env bash
# 一次配置 CLI 依赖、用户级启动命令与 Bash/Zsh 的 PATH。
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
venv_dir="$repo_dir/rdk/.venv"
bin_dir="$HOME/.local/bin"
python_command=python3
launcher_only=0

usage() {
    cat <<'HELP'
用法：bash setup.sh [选项]

默认创建或复用 rdk/.venv，安装 CLI，并配置任意目录可用的 ros-cli。
需要 Python 3.10+ 和 venv；首次安装依赖需要网络。无需 sudo。

选项：
  --python 路径       指定创建虚拟环境的 Python（默认 python3）
  --venv 路径         指定虚拟环境位置（默认 rdk/.venv）
  --bin-dir 路径      指定启动命令目录（默认 ~/.local/bin）
  --launcher-only     CLI 已安装时，仅修复启动入口和 PATH，不联网安装
  -h, --help          显示帮助
HELP
}

while (($#)); do
    case "$1" in
        --python|--venv|--bin-dir)
            if (($# < 2)) || [[ -z "$2" || "$2" == --* ]]; then
                printf '错误：%s 需要提供一个值。\n' "$1" >&2
                exit 2
            fi
            case "$1" in
                --python) python_command="$2" ;;
                --venv) venv_dir="$2" ;;
                --bin-dir) bin_dir="$2" ;;
            esac
            shift 2
            ;;
        --launcher-only) launcher_only=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) printf '错误：无法识别选项 %s；请运行 bash setup.sh --help。\n' "$1" >&2; exit 2 ;;
    esac
done

if ! command -v "$python_command" >/dev/null 2>&1; then
    printf '错误：找不到 %s，请安装 Python 3.10+，或用 --python 指定解释器。\n' "$python_command" >&2
    exit 1
fi
if ! "$python_command" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    printf '错误：需要 Python 3.10 或更高版本。\n' >&2
    exit 1
fi
venv_dir="$("$python_command" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$venv_dir")"
bin_dir="$("$python_command" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$bin_dir")"

if [[ ! -f "$venv_dir/pyvenv.cfg" ]]; then
    if [[ "$launcher_only" == 1 || -e "$venv_dir" ]]; then
        printf '错误：%s 不是可用的虚拟环境；请选择空闲路径或先完成正常安装。\n' "$venv_dir" >&2
        exit 1
    fi
    printf '正在创建虚拟环境：%s\n' "$venv_dir"
    if ! "$python_command" -m venv "$venv_dir"; then
        printf '错误：无法创建虚拟环境。Ubuntu 可先安装 python3-venv，再选择新的 --venv 路径重试。\n' >&2
        exit 1
    fi
fi
venv_python="$venv_dir/bin/python"
if [[ ! -x "$venv_python" ]] || ! "$venv_python" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    printf '错误：虚拟环境的 Python 不可用或低于 3.10；请用 --venv 选择新的环境。\n' >&2
    exit 1
fi

if [[ "$launcher_only" == 0 ]]; then
    if ! "$venv_python" -m pip --version >/dev/null 2>&1; then
        "$venv_python" -m ensurepip
    fi
    printf '正在安装 CLI 与运行依赖……\n'
    if ! "$venv_python" -m pip install --disable-pip-version-check --no-input -e "$repo_dir/templates" -e "$repo_dir/rdk"; then
        printf '错误：CLI 安装失败，请检查以上依赖和网络错误，再运行本脚本。\n' >&2
        exit 1
    fi
fi

if ! "$venv_python" -I -c 'import rdk_cli.main, rdk_cli.tui' || [[ ! -x "$venv_dir/bin/ros-cli" ]]; then
    printf '错误：CLI 或全屏界面依赖不完整，请去掉 --launcher-only 重新安装。\n' >&2
    exit 1
fi

"$venv_python" "$repo_dir/rdk/scripts/configure_launcher.py" --venv "$venv_dir" --bin-dir "$bin_dir"

# 在独立临时目录验收，确保启动不依赖仓库是当前目录。
probe_dir="$(mktemp -d)"
trap 'rm -rf -- "$probe_dir"' EXIT
(
    cd -- "$probe_dir"
    "$bin_dir/ros-cli" --version
    "$bin_dir/ros-cli" template list >/dev/null
)
printf '\n配置完成！新开一个终端，在任意目录输入 ros-cli 即可打开全屏界面。\n'
printf '按 Ctrl+Q 退出；查看帮助使用 ros-cli --help。\n'
case ":$PATH:" in
    *:"$bin_dir":*) printf '当前终端的 PATH 已包含启动目录，现在也可以直接运行 ros-cli。\n' ;;
    *) printf '当前终端若要立即使用，请执行：export PATH=%q:"$PATH"\n' "$bin_dir" ;;
esac
