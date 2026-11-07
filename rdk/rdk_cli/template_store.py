"""模板版本、发布状态与参数管理；导入过程只复制文件，不运行模板代码。"""

import json
import keyword
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from urllib.request import urlopen

NAME = r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*'
VERSION = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
KINDS = {'ros2_python', 'ros2_cpp', 'ros2_bringup', 'pytorch', 'directory'}
BUILTIN_ROOT = Path(str(files('rdk_templates')))
CPP_KEYWORDS = set(('alignas alignof and asm auto bool break case catch char class const '
                    'constexpr continue decltype default delete do double else enum explicit '
                    'export extern false float for friend goto if inline int long mutable '
                    'namespace new noexcept not nullptr operator or private protected public '
                    'register reinterpret_cast return short signed sizeof static struct switch '
                    'template this thread_local throw true try typedef typeid typename union '
                    'unsigned using virtual void volatile wchar_t while xor concept requires '
                    'co_await co_return co_yield').split())


class TemplateError(ValueError):
    """可直接显示给用户的模板错误。"""


def store_root():
    return Path(os.environ.get('ROBOT_CLI_TEMPLATE_HOME',
                               str(Path.home() / '.local/share/robot-cli/templates'))).expanduser()


def split_reference(reference):
    name, sep, version = reference.partition('@')
    aliases = {alias: item['name'] for item in inventory() for alias in item.get('aliases', [])}
    name = aliases.get(name, name)
    if not re.fullmatch(NAME, name) or (sep and not re.fullmatch(VERSION, version)):
        raise TemplateError('模板引用应为 name 或 name@MAJOR.MINOR.PATCH（例如 ros2-cpp@1.0.0）')
    return name, version if sep else None


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise TemplateError(f'无法读取 JSON {path}：{error}') from error


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise TemplateError('template.json 必须是 JSON 对象')
    for field in ('name', 'version', 'description', 'maintainer', 'kind', 'status'):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise TemplateError(f'模板元数据缺少非空字符串：{field}')
    if not re.fullmatch(NAME, manifest['name']) or not re.fullmatch(VERSION, manifest['version']):
        raise TemplateError('模板元数据必须使用规范名称，不能使用别名')
    if manifest['kind'] not in KINDS:
        raise TemplateError(f'不支持的模板 kind：{manifest["kind"]}')
    if manifest['status'] not in {'draft', 'published'}:
        raise TemplateError('status 必须是 draft 或 published')
    for field in ('environment', 'dependencies', 'changelog', 'ros_distro'):
        value = manifest.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise TemplateError(f'{field} 必须是字符串列表')
    if manifest['kind'].startswith('ros2_') and (not manifest['ros_distro'] or
            not set(manifest['ros_distro']) <= {'humble', 'jazzy'}):
        raise TemplateError('ROS 生成器仅支持 humble/jazzy，ros_distro 必须为其非空子集')
    if 'compatibility' in manifest:
        from rdk_cli.environments.compatibility import validate_compatibility
        try:
            validate_compatibility(manifest['compatibility'])
        except ValueError as error:
            raise TemplateError(str(error)) from error
    aliases = manifest.get('aliases', [])
    if not isinstance(aliases, list) or any(not isinstance(alias, str) or not re.fullmatch(NAME, alias) for alias in aliases):
        raise TemplateError('aliases 必须是合法模板名称的列表')
    validate_generation(manifest.get('generation', {}))
    parameters = manifest.get('parameters')
    if not isinstance(parameters, dict):
        raise TemplateError('parameters 必须是对象')
    for key, spec in parameters.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', key) or not isinstance(spec, dict):
            raise TemplateError(f'无效的参数定义：{key}')
        if not isinstance(spec.get('type'), str) or spec['type'] not in {'string', 'integer', 'number', 'boolean'}:
            raise TemplateError(f'参数 {key} 的 type 不受支持')
        if 'label' in spec and not isinstance(spec['label'], str):
            raise TemplateError(f'参数 {key} 的 label 必须是字符串')
        if 'required' in spec and not isinstance(spec['required'], bool):
            raise TemplateError(f'参数 {key} 的 required 必须为布尔值')
        if 'pattern' in spec:
            try:
                re.compile(spec['pattern'])
            except (re.error, TypeError) as error:
                raise TemplateError(f'参数 {key} 的正则表达式无效') from error
        if 'enum' in spec and (not isinstance(spec['enum'], list) or not spec['enum']):
            raise TemplateError(f'参数 {key} 的 enum 必须为非空列表')
        for bound in ('minimum', 'maximum'):
            if bound in spec and (type(spec[bound]) not in (int, float) or not math.isfinite(spec[bound])):
                raise TemplateError(f'参数 {key} 的 {bound} 必须是有限数值')
        if 'default' in spec:
            validate_value(key, spec['default'], spec)
    if 'package_name' not in parameters or parameters['package_name']['type'] != 'string':
        raise TemplateError('parameters 必须包含 string 类型的 package_name')
    return manifest


def validate_generation(generation):
    if not isinstance(generation, dict):
        raise TemplateError('generation 必须是对象')
    allowed = {'skeleton', 'ci', 'skeleton_ci', 'next_steps', 'skeleton_next_steps',
               'smoke_engine', 'smoke_commands', 'skeleton_smoke_commands', 'ros'}
    if generation.keys() - allowed:
        raise TemplateError(f'未知 generation 字段：{", ".join(sorted(generation.keys() - allowed))}')
    for key in ('skeleton', 'ci', 'skeleton_ci'):
        value = generation.get(key)
        if key in generation and (not isinstance(value, str) or not value or
                                  Path(value).is_absolute() or '..' in Path(value).parts):
            raise TemplateError(f'generation.{key} 必须是模板内的相对路径')
    for key in ('next_steps', 'skeleton_next_steps'):
        value = generation.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise TemplateError(f'generation.{key} 必须是字符串列表')
    for key in ('smoke_commands', 'skeleton_smoke_commands'):
        value = generation.get(key, [])
        if not isinstance(value, list) or any(not isinstance(command, list) or not command or
                any(not isinstance(arg, str) for arg in command) for command in value):
            raise TemplateError(f'generation.{key} 必须是非空 argv 列表组成的列表')
    if 'smoke_engine' in generation and generation['smoke_engine'] != 'ros2':
        raise TemplateError('generation.smoke_engine 仅支持 ros2；其他测试请使用 smoke_commands')
    ros = generation.get('ros', {})
    if not isinstance(ros, dict):
        raise TemplateError('generation.ros 必须是对象')
    if ros.get('build_type', 'ament_cmake') not in {'ament_python', 'ament_cmake'}:
        raise TemplateError('generation.ros.build_type 必须为 ament_python 或 ament_cmake')
    for key in ('node_dependency', 'test_dependency'):
        if ros.get(key) is not None and (not isinstance(ros[key], str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', ros[key])):
            raise TemplateError(f'generation.ros.{key} 必须为依赖包名称或 null')
    for key in ('runtime_dependencies', 'example_dependencies'):
        value = ros.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', item) for item in value):
            raise TemplateError(f'generation.ros.{key} 必须为依赖包名称列表')


def state():
    path = store_root() / 'state.json'
    result = read_json(path) if path.exists() else {}
    if not isinstance(result, dict) or any(not isinstance(value, bool) for value in result.values()):
        raise TemplateError('模板启停状态文件必须是布尔值组成的 JSON 对象')
    return result


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def inventory():
    records = []
    enabled = state()
    paths = list(BUILTIN_ROOT.glob('*/template.json'))
    paths += list(store_root().glob('*/*/template.json'))
    seen = set()
    for path in sorted(paths):
        manifest = validate_manifest(read_json(path))
        identity = f"{manifest['name']}@{manifest['version']}"
        if identity in seen:
            raise TemplateError(f'模板版本重复：{identity}')
        seen.add(identity)
        records.append({**manifest, 'path': path.parent,
                        'enabled': enabled.get(identity, manifest['status'] == 'published'),
                        'builtin': path.is_relative_to(BUILTIN_ROOT)})
    names = {record['name'] for record in records}
    aliases = {}
    for record in records:
        for alias in record.get('aliases', []):
            if alias in names or (alias in aliases and aliases[alias] != record['name']):
                raise TemplateError(f'模板别名冲突：{alias}')
            aliases[alias] = record['name']
    return records


def resolve(reference, usable=False):
    name, version = split_reference(reference)
    records = [item for item in inventory() if item['name'] == name and
               (version is None or item['version'] == version)]
    if usable and version is None:
        records = [item for item in records if item['enabled'] and item['status'] == 'published']
    if not records:
        raise TemplateError(f'找不到模板或没有已发布且启用的版本：{reference}；请运行 template list')
    record = max(records, key=lambda item: tuple(map(int, item['version'].split('.'))))
    if usable and (not record['enabled'] or record['status'] != 'published'):
        raise TemplateError(f'模板 {reference} 已停用或尚未发布')
    return record


def set_enabled(reference, enabled):
    record = resolve(reference)
    if enabled and record['status'] != 'published':
        raise TemplateError('草稿模板必须先通过 template publish 记录评审后才能启用')
    flags = state()
    flags[f"{record['name']}@{record['version']}"] = enabled
    save_json(store_root() / 'state.json', flags)
    return record


def validate_value(key, value, spec):
    expected = {'string': str, 'integer': int, 'number': (int, float), 'boolean': bool}[spec['type']]
    if not isinstance(value, expected) or (spec['type'] in {'integer', 'number'} and isinstance(value, bool)):
        raise TemplateError(f'参数 {key} 必须为 {spec["type"]}')
    if spec['type'] == 'number' and not math.isfinite(value):
        raise TemplateError(f'参数 {key} 必须为有限数值')
    if 'enum' in spec and value not in spec['enum']:
        raise TemplateError(f'参数 {key} 必须是 {spec["enum"]} 之一')
    if 'pattern' in spec and not re.fullmatch(spec['pattern'], str(value)):
        raise TemplateError(f'参数 {key} 不符合格式：{spec["pattern"]}')
    for bound in ('minimum', 'maximum'):
        if bound in spec:
            if type(spec[bound]) not in (int, float) or not math.isfinite(spec[bound]):
                raise TemplateError(f'参数 {key} 的 {bound} 必须是有限数值')
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TemplateError(f'参数 {key} 的数值范围只能用于数字')
            if (bound == 'minimum' and value < spec[bound]) or (bound == 'maximum' and value > spec[bound]):
                raise TemplateError(f'参数 {key} 超出范围：{bound}={spec[bound]}')
    if spec.get('required') and isinstance(value, str) and not value.strip():
        raise TemplateError(f'必填参数 {key} 不能为空')
    return value


def parameters(record, supplied):
    specs = record['parameters']
    unknown = supplied.keys() - specs.keys()
    if unknown:
        raise TemplateError(f'未知模板参数：{", ".join(sorted(unknown))}')
    values = {}
    for key, spec in specs.items():
        value = supplied.get(key, spec.get('default'))
        if value is None:
            if spec.get('required'):
                raise TemplateError(f'缺少必填模板参数：{key}')
            continue
        if key in supplied and spec['type'] != 'string':
            try:
                value = json.loads(value)
            except (ValueError, TypeError) as error:
                raise TemplateError(f'参数 {key} 需要 JSON {spec["type"]} 值') from error
        values[key] = validate_value(key, value, spec)
    package = values.get('package_name', '')
    if package and (keyword.iskeyword(package) or package in CPP_KEYWORDS):
        raise TemplateError(f'项目名不能使用 Python/C++ 关键字：{package}')
    return values


def create_draft(name, version, maintainer, kind):
    manifest = {
        'name': name, 'version': version, 'description': f'{name} 团队模板',
        'kind': kind, 'status': 'draft', 'maintainer': maintainer,
        'environment': ['Python >= 3.10'], 'dependencies': [],
        'ros_distro': ['jazzy'] if kind.startswith('ros2_') else [],
        'changelog': [f'{version}: 初始化模板'],
        'parameters': {'package_name': {'type': 'string', 'required': True,
                                       'pattern': '[a-z](?:[a-z0-9_]*[a-z0-9])?'}},
    }
    validate_manifest(manifest)
    if any(item['name'] == name and item['version'] == version for item in inventory()):
        raise TemplateError(f'模板版本已存在，发布版本不可覆盖：{name}@{version}')
    destination = store_root() / name / version
    destination.mkdir(parents=True, exist_ok=False)
    save_json(destination / 'template.json', manifest)
    (destination / 'README.md').write_text('# {{package_name}}\n\n请在发布前补齐运行说明和测试。\n', encoding='utf-8')
    return destination


def publish(reference, reviewer):
    record = resolve(reference)
    if record['builtin'] or record['status'] == 'published':
        raise TemplateError('该版本已发布且不可修改；请新建版本')
    if not reviewer.strip():
        raise TemplateError('--reviewed-by 不能为空，发布前请完成团队评审')
    manifest = read_json(record['path'] / 'template.json')
    manifest['status'] = 'published'
    manifest['review'] = {'reviewed_by': reviewer, 'recorded_at': datetime.now(timezone.utc).isoformat()}
    save_json(record['path'] / 'template.json', manifest)
    set_enabled(reference, True)
    return record


def import_template(source, ref=None, subdir='.', registry=None):
    """支持本地目录、Git URL，以及引用 Git 条目的 JSON 注册表。"""
    if registry:
        if registry.startswith(('https://', 'http://')):
            try:
                with urlopen(registry, timeout=30) as response:
                    catalog = json.load(response)
            except (OSError, ValueError) as error:
                raise TemplateError(f'无法读取注册表：{error}') from error
        else:
            catalog = read_json(Path(registry).expanduser())
        try:
            entry = catalog['templates'][source]
            git_source, ref, subdir = entry['git'], entry.get('ref'), entry.get('subdir', '.')
        except (KeyError, TypeError) as error:
            raise TemplateError('注册表条目应包含 git，以及可选 ref、subdir') from error
        reference = source
        source = git_source
    else:
        reference = None
    if not isinstance(source, str) or source.startswith('-'):
        raise TemplateError('无效的模板来源')
    if not isinstance(subdir, str) or Path(subdir).is_absolute() or '..' in Path(subdir).parts:
        raise TemplateError('--subdir 必须是仓库内的相对路径')
    with tempfile.TemporaryDirectory(prefix='robot-cli-import-') as temporary:
        local = Path(source).expanduser()
        commit = None
        if local.is_dir() and ref is None:
            checkout = local.resolve()
        else:
            checkout = Path(temporary) / 'repo'
            try:
                subprocess.run(['git', '-c', 'protocol.ext.allow=never', 'clone', '--no-checkout',
                                '--', source, str(checkout)], check=True, capture_output=True, text=True)
                if ref is not None and (not isinstance(ref, str) or ref.startswith('-')):
                    raise TemplateError('无效的 Git ref')
                subprocess.run(['git', '-C', str(checkout), 'checkout', '--detach', ref or 'HEAD'],
                               check=True, capture_output=True, text=True)
                commit = subprocess.run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'],
                                        check=True, capture_output=True, text=True).stdout.strip()
            except (OSError, subprocess.CalledProcessError) as error:
                raise TemplateError(f'Git 导入失败：{error}；请检查 URL、ref 和访问权限') from error
        root = checkout / subdir
        if root.is_symlink() or not root.resolve().is_relative_to(checkout.resolve()):
            raise TemplateError('模板目录不能通过符号链接跳出仓库')
        manifest = validate_manifest(read_json(root / 'template.json'))
        if reference:
            expected_name, expected_version = split_reference(reference)
            if manifest['name'] != expected_name or (expected_version and manifest['version'] != expected_version):
                raise TemplateError('注册表引用与下载的模板名称/版本不一致')
        identity = f"{manifest['name']}@{manifest['version']}"
        if any(f"{item['name']}@{item['version']}" == identity for item in inventory()):
            raise TemplateError(f'模板版本已存在，不能覆盖：{identity}')
        for path in root.rglob('*'):
            if '.git' in path.relative_to(root).parts:
                continue
            if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                raise TemplateError(f'模板不允许符号链接或特殊文件：{path}')
        destination = store_root() / manifest['name'] / manifest['version']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root, destination, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        manifest['status'] = 'draft'
        manifest.pop('review', None)
        manifest['source'] = {'location': source, 'ref': ref, 'commit': commit, 'subdir': subdir}
        save_json(destination / 'template.json', manifest)
        return destination
