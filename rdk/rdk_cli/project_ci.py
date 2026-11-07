"""读取模板声明的独立项目 CI 工作流。"""
from rdk_cli.project_files import render_text, template_path
from rdk_cli.template_store import TemplateError


def workflow_for(record, values, *, include_examples=True):
    key = 'ci' if include_examples else 'skeleton_ci'
    source = record.get('generation', {}).get(key)
    if not source:
        raise TemplateError(f'模板未声明 {key} 工作流，请在 template.json 中配置')
    return render_text(template_path(record, source).read_text(encoding='utf-8'), values)
