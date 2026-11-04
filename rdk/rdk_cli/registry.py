"""兼容旧导入；模板清单由版本化的 template.json 驱动。"""
from rdk_cli.template_store import inventory

TEMPLATES = {item['name']: item for item in inventory()}
