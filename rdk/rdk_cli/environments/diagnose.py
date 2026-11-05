"""将可识别的包管理错误补充为中文操作建议，保留原始错误。"""
import re


def explain_build_failure(output: str) -> str | None:
    """把已知的 apt/pip 失败模式翻译成中文建议，无法识别时返回 None。"""
    if re.search(r"Version ['\"].+?['\"] for ['\"].+?['\"] was not found", output):
        return ('锁里指定的版本在当前源中不可用，可能是该版本已从源上撤下，或源配置不匹配。'
                '请先核对 apt.lock 中的包名、版本与目标环境的软件源。'
                '可选择使用 robot-cli env configure <profile> --update-lock 显式更新整份锁，'
                '审查差异后改用当前可用版本并验证依赖，'
                '或中止构建，保留原锁并向团队归档查找该版本；不会自动换包。')
    if 'Unable to locate package' in output:
        return ('该包在当前源里不存在，可能是源配置或发行版不匹配。请检查 --root 下该环境的'
                ' Dockerfile 和锁文件，并核对目标镜像内 /etc/apt/sources.list'
                ' 与 /etc/apt/sources.list.d/ 的源配置。')
    if re.search(r'Could not resolve|Temporary failure resolving|Temporary failure in name resolution|'
                 r'Could not connect|Connection (?:timed out|refused)|Network is unreachable|'
                 r'Failed to establish a new connection|Read timed out', output, re.IGNORECASE):
        return '拉取源失败，检查网络、DNS、代理或镜像配置，再重试构建。'
    return None
