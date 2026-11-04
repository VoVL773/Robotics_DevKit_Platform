"""开发环境兼容矩阵，名称与版本是镜像和锁文件的稳定标识。"""
from dataclasses import asdict, dataclass


class EnvironmentError(RuntimeError):
    """可直接呈现的开发环境错误。"""


@dataclass(frozen=True)
class Profile:
    name: str
    ros: str
    ubuntu: str
    python: str
    base: str
    gpu: bool = False
    cuda: str | None = None
    driver_min: str | None = None
    torch: str | None = None
    version: str = '1.0.0'
    architecture: str = 'amd64'

    @property
    def image(self):
        return f'robot-cli/{self.name}:{self.version}'

    @property
    def container(self):
        return f'robot-cli-{self.name}-{self.version.replace(".", "-")}'

    def data(self):
        return asdict(self)


PROFILES = {}
for ros, ubuntu, python in [('humble', '22.04', '3.10'), ('jazzy', '24.04', '3.12')]:
    name = f'ros2-{ros}-dev'
    PROFILES[name] = Profile(name, ros, ubuntu, python, f'ros:{ros}-ros-base')
    gpu_name = name + '-gpu'
    PROFILES[gpu_name] = Profile(
        gpu_name, ros, ubuntu, python,
        f'nvidia/cuda:12.6.3-devel-ubuntu{ubuntu}', True, '12.6', '560.35.05', '2.6.0+cu126',
    )


def get_profile(name: str) -> Profile:
    name = name.replace('hamble', 'humble')
    try:
        return PROFILES[name]
    except KeyError as error:
        raise EnvironmentError(f'未知环境 {name}；可选：{", ".join(PROFILES)}') from error
