"""终端配色主题：全屏工作台、问答向导和子命令共用同一套可持久化颜色。

颜色统一存放为十六进制值，TUI 通过 Textual 主题变量使用，
rich 输出直接读取当前主题；选择写入用户配置目录，下次启动自动恢复。
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = 'theme.json'
DEFAULT = 'deep-blue'
ENV_VAR = 'ROBOT_CLI_THEME'
CONFIG_HOME_VAR = 'ROBOT_CLI_CONFIG_HOME'


class ThemeError(ValueError):
    """主题名称无效或配置文件不可写。"""


@dataclass(frozen=True)
class ThemeSpec:
    name: str
    label: str
    description: str
    dark: bool
    colors: dict[str, str] = field(default_factory=dict)


THEMES = {
    'deep-blue': ThemeSpec(
        name='deep-blue',
        label='深海蓝',
        description='深色底 + 青蓝强调，适合长时间编码。',
        dark=True,
        colors={
            'background': '#171c23',
            'background_dark': '#0e1319',
            'surface': '#1f2a37',
            'accent': '#67d5ff',
            'accent_strong': '#37b8ef',
            'border': '#299bcc',
            'panel': '#123247',
            'header_text': '#e0f5ff',
            'text': '#dae4ee',
            'muted': '#94a8bc',
            'tabbar': '#202b37',
            'job_background': '#203344',
            'log_background': '#10151b',
            'error': '#ff8e91',
            'warning': '#f3c969',
            'success': '#7ee787',
            'boost': '#2c3b49',
        },
    ),
    'neon-night': ThemeSpec(
        name='neon-night',
        label='霓虹紫',
        description='近黑底 + 紫红霓虹强调，对比强烈。',
        dark=True,
        colors={
            'background': '#0d0716',
            'background_dark': '#07040d',
            'surface': '#191026',
            'accent': '#00e5ff',
            'accent_strong': '#ff2ed0',
            'border': '#8a3cff',
            'panel': '#2b1240',
            'header_text': '#f5eaff',
            'text': '#ece6ff',
            'muted': '#a08cc2',
            'tabbar': '#1d1330',
            'job_background': '#241436',
            'log_background': '#07040d',
            'error': '#ff4d6d',
            'warning': '#ffd166',
            'success': '#4bffa5',
            'boost': '#2f1c48',
        },
    ),
}

ORDER = tuple(THEMES)

# Textual 主题自带的变量之外，界面还需要以下自定义变量。
_TUI_VARIABLES = {
    'header_text': 'rdk-header-text',
    'muted': 'rdk-muted',
    'tabbar': 'rdk-tabbar',
    'job_background': 'rdk-job-bg',
    'log_background': 'rdk-log-bg',
}

_cache: ThemeSpec | None = None


def config_root() -> Path:
    """用户配置目录；测试可用 ROBOT_CLI_CONFIG_HOME 隔离。"""
    override = os.environ.get(CONFIG_HOME_VAR)
    if override:
        return Path(override).expanduser()
    base = os.environ.get('XDG_CONFIG_HOME')
    return (Path(base).expanduser() if base else Path.home() / '.config') / 'robot-cli'


def config_path() -> Path:
    return config_root() / CONFIG_FILE


def active_name() -> str:
    """环境变量优先，其次用户配置，最后默认；无效值回退默认主题。"""
    override = os.environ.get(ENV_VAR)
    if override:
        return override if override in THEMES else DEFAULT
    try:
        data = json.loads(config_path().read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return DEFAULT
    name = data.get('theme') if isinstance(data, dict) else None
    return name if name in THEMES else DEFAULT


def active() -> ThemeSpec:
    global _cache
    if _cache is None:
        _cache = THEMES[active_name()]
    return _cache


def reset_cache() -> None:
    """仅供测试：环境变量或配置文件变更后重新读取。"""
    global _cache
    _cache = None


def set_active(name: str) -> ThemeSpec:
    """校验并保存主题，供后续运行与全屏工作台使用。"""
    global _cache
    if name not in THEMES:
        choices = '、'.join(record.label for record in THEMES.values())
        raise ThemeError(f'未知主题 {name!r}；可选：{choices}')
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'theme': name}, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
    except OSError as error:
        raise ThemeError(f'无法写入主题配置 {path}：{error}') from error
    _cache = THEMES[name]
    return _cache


def css_variables(spec: ThemeSpec) -> dict[str, str]:
    return {variable: spec.colors[key] for key, variable in _TUI_VARIABLES.items()}


def _theme_variables(spec: ThemeSpec) -> dict[str, str]:
    """自定义变量与 Textual 内置变量的覆盖值，保证高亮块上的文字可读。"""
    variables = css_variables(spec)
    variables.update({
        'footer-background': spec.colors['panel'],
        'footer-foreground': spec.colors['header_text'],
        'footer-key-foreground': spec.colors['header_text'],
        'footer-description-foreground': spec.colors['header_text'],
        # 亮色强调背景上的按钮、光标行与选中行需要深色文字。
        'button-color-foreground': spec.colors['background'],
        'block-cursor-foreground': spec.colors['background'],
    })
    return variables


def css_variable_defaults() -> dict[str, str]:
    """Textual 解析 CSS 时的兜底变量，避免未注册主题时报错。"""
    return css_variables(THEMES[DEFAULT])


def textual_theme(spec: ThemeSpec):
    """把配色映射为 Textual Theme；延迟导入，子命令无需加载 TUI 依赖。"""
    from textual.theme import Theme

    return Theme(
        name=spec.name,
        primary=spec.colors['accent'],
        secondary=spec.colors['border'],
        accent=spec.colors['accent_strong'],
        foreground=spec.colors['text'],
        background=spec.colors['background'],
        surface=spec.colors['surface'],
        panel=spec.colors['panel'],
        boost=spec.colors['boost'],
        success=spec.colors['success'],
        warning=spec.colors['warning'],
        error=spec.colors['error'],
        dark=spec.dark,
        variables=_theme_variables(spec),
    )
