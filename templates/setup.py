"""自动收集模板目录中的资源，包含控制文件和隐藏占位文件。"""
from pathlib import Path
from setuptools import setup

root = Path(__file__).parent / 'rdk_templates'
resources = []
for directory in sorted(root.iterdir()):
    manifest = directory / 'template.json'
    if not manifest.is_file():
        continue
    for path in directory.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            resources.append(path.relative_to(root).as_posix())
setup(package_data={'rdk_templates': resources}, include_package_data=False)
