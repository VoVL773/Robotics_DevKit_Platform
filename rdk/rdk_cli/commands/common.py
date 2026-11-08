"""命令行统一错误出口；业务模块只抛异常，不终止 CLI。"""
import typer

from rdk_cli import terminal as ui


def fail(message: str) -> None:
    ui.error(message)
    raise typer.Exit(code=1)
