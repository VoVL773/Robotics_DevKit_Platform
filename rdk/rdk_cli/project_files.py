"""模板文件渲染与 ROS package.xml 资源补全，不依赖命令或界面。"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from rdk_cli import template_store as store


def render_template(record, destination, values, *, source_dir=None):
    """仅进行文本替换与文件复制；禁止符号链接、路径越界和未解析的占位符。"""
    root = record['path'] if source_dir is None else template_path(record, source_dir)
    if not root.is_dir():
        raise store.TemplateError(f'模板内容目录不存在：{root}')
    rendered = {}
    def replace(text):
        return render_text(text, values)

    for source in sorted(root.rglob('*')):
        relative = source.relative_to(root)
        if (any(part in {'.git', '__pycache__'} for part in relative.parts)
                or (source_dir is None and relative.parts[0] == '.rdp') or source.suffix == '.pyc'):
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


def template_path(record, relative):
    """配置引用必须指向模板内的普通文件或目录，禁止越界和符号链接。"""
    root = Path(record['path']).resolve()
    candidate = Path(relative)
    if candidate.is_absolute() or '..' in candidate.parts:
        raise store.TemplateError(f'模板资源路径必须位于模板内：{relative}')
    path = root / candidate
    if not path.resolve().is_relative_to(root) or any(
            parent.is_symlink() for parent in [path, *path.parents] if parent != root and root in parent.parents):
        raise store.TemplateError(f'模板资源不允许符号链接或路径越界：{relative}')
    if not path.exists():
        raise store.TemplateError(f'模板资源不存在：{relative}')
    return path


def render_text(text, values):
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', str(value))
    if re.search(r'\{\{[a-z][a-z0-9_]*\}\}', text):
        raise store.TemplateError('模板包含未定义的参数占位符')
    return text


def add_runtime_dependencies(project_path, ros, *, include_examples=True):
    """ROS 通用元数据适配；依赖名称由模板 generation.ros 声明。"""
    package_xml = project_path / 'package.xml'
    tree = ET.parse(package_xml)
    root = tree.getroot()
    dependencies = list(ros.get('runtime_dependencies', []))
    if include_examples:
        dependencies += ros.get('example_dependencies', [])
    for dependency in dependencies:
        if not any(child.text == dependency for child in root if child.tag in {'depend', 'exec_depend'}):
            ET.SubElement(root, 'exec_depend').text = dependency
    test_dependency = ros.get('test_dependency')
    if include_examples and test_dependency and not any(child.text == test_dependency for child in root):
        ET.SubElement(root, 'test_depend').text = test_dependency
    for filename in ('test_copyright.py', 'test_flake8.py', 'test_pep257.py'):
        (project_path / 'test' / filename).unlink(missing_ok=True)
    ET.indent(tree, space='  ')
    tree.write(package_xml, encoding='utf-8', xml_declaration=True)
