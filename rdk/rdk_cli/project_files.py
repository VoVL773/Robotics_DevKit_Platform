"""模板文件渲染与 ROS package.xml 资源补全，不依赖命令或界面。"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from rdk_cli import template_store as store


def render_template(record, destination, values):
    """仅进行文本替换与文件复制；禁止符号链接、路径越界和未解析的占位符。"""
    root = record['path']
    rendered = {}
    def replace(text):
        for key, value in values.items():
            text = text.replace('{{' + key + '}}', str(value))
        if re.search(r'\{\{[a-z][a-z0-9_]*\}\}', text):
            raise store.TemplateError('模板包含未定义的参数占位符')
        return text

    for source in sorted(root.rglob('*')):
        relative = source.relative_to(root)
        if any(part in {'.git', '__pycache__'} for part in relative.parts) or source.suffix == '.pyc':
            continue
        if relative == Path('template.json'):
            continue
        if source.is_symlink():
            raise store.TemplateError(f'模板包含不支持的符号链接：{relative}')
        target = destination / replace(str(relative))
        if not target.resolve().is_relative_to(destination.resolve()):
            raise store.TemplateError(f'模板路径越界：{relative}')
        if source.is_dir():
            continue
        if not source.is_file():
            raise store.TemplateError(f'模板包含特殊文件：{relative}')
        if target in rendered:
            raise store.TemplateError(f'参数替换后路径重复：{relative}')
        content = source.read_bytes()
        try:
            content = replace(content.decode('utf-8')).encode('utf-8')
        except UnicodeDecodeError:
            pass
        rendered[target] = content
    # 先校验全部内容，再写入，避免模板错误留下半成品。
    for target, content in rendered.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def add_runtime_dependencies(project_path, kind):
    package_xml = project_path / 'package.xml'
    tree = ET.parse(package_xml)
    root = tree.getroot()
    dependencies = ['launch_ros', 'ament_index_python']
    if kind == 'ros2_bringup':
        dependencies += ['demo_nodes_cpp', 'python3-yaml']
    for dependency in dependencies:
        if not any(child.text == dependency for child in root if child.tag in {'depend', 'exec_depend'}):
            ET.SubElement(root, 'exec_depend').text = dependency
    tests = {'ros2_cpp': 'ament_cmake_gtest', 'ros2_python': 'python3-pytest',
             'ros2_bringup': 'ament_cmake_pytest'}
    if not any(child.text == tests[kind] for child in root):
        ET.SubElement(root, 'test_depend').text = tests[kind]
    # ros2 pkg create 生成的版权/style 占位测试与本模板无关；由行为测试替代。
    test_dir = project_path / 'test'
    for filename in ('test_copyright.py', 'test_flake8.py', 'test_pep257.py'):
        (test_dir / filename).unlink(missing_ok=True)
    ET.indent(tree, space='  ')
    tree.write(package_xml, encoding='utf-8', xml_declaration=True)
