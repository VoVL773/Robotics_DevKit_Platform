"""从模板自己的骨架目录生成无示例工程。"""
import shutil

from rdk_cli.project_files import render_template


def render_skeleton(record, destination, values):
    values = {**{key: spec['default'] for key, spec in record['parameters'].items() if 'default' in spec},
              'template_id': record['name'], 'template_version': record['version'], **values}
    source = record.get('generation', {}).get('skeleton')
    if source:
        shutil.rmtree(destination / 'test', ignore_errors=True)
        render_template(record, destination, values, source_dir=source)
        return
    # 未声明骨架的旧版/外部模板仅提供通用空目录，不猜测业务文件。
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'README.md').write_text(
        f'# {values["package_name"]}\n\n本项目未生成示例代码，请添加自己的实现与测试。\n', encoding='utf-8')
    for folder in ('src', 'config', 'docs'):
        path = destination / folder / '.gitkeep'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
