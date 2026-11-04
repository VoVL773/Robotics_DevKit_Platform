"""独立于界面的异步命令执行器，负责日志流与整个进程组的清理。"""
import asyncio
import os
import signal
from collections.abc import Callable, Sequence


class ProcessRunner:
    def __init__(self):
        self.process = None

    async def run(self, command: Sequence[str], on_line: Callable[[str], None],
                  cancelled: Callable[[], bool]) -> int:
        """执行命令并逐行通知调用者；取消状态由调用者持有。"""
        try:
            self.process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                start_new_session=True, limit=1024 * 1024,
                env={**os.environ, 'PYTHONUNBUFFERED': '1', 'NO_COLOR': '1', 'TERM': 'dumb',
                     'GIT_TERMINAL_PROMPT': '0', 'GIT_SSH_COMMAND': 'ssh -o BatchMode=yes'},
            )
            # 启动期间也可能收到退出请求，赋值后再次检查以免遗漏进程。
            if cancelled():
                await self.terminate()
            while True:
                chunk = await self.process.stdout.readline()
                if not chunk:
                    break
                on_line(chunk.decode('utf-8', errors='replace').rstrip())
            return await self.process.wait()
        finally:
            await self.terminate()
            self.process = None

    async def terminate(self):
        process = self.process
        if process is None:
            return
        # 父进程已退出时也清理同组后代（如 colcon、CMake、Git）。
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=3)
        except asyncio.TimeoutError:
            pass
        # 后代可能忽略 SIGTERM，不能只依据组长的退出状态判断。
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
