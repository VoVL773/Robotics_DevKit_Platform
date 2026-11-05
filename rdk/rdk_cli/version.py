"""从安装元数据读取 CLI 版本，供界面、项目记录和容器导出共用。"""
from importlib import metadata


def cli_version() -> str:
    """源码未安装时仍允许显示版本和生成项目。"""
    try:
        return metadata.version('robot-cli')
    except metadata.PackageNotFoundError:
        return '0.0.0+unknown'
