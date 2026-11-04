"""命令行统一错误出口；业务模块只抛异常，不终止 CLI。"""
import typer


def fail(message: str) -> None:
    typer.secho(f'错误：{message}', fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)
