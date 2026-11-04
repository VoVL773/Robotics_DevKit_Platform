"""模板声明的兼容矩阵，保持旧团队模板的无声明格式向后兼容。"""
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version



def validate_compatibility(value):
    if not isinstance(value, dict):
        raise ValueError('compatibility 必须是对象')
    platforms = value.get('platforms')
    if not isinstance(platforms, list) or not platforms:
        raise ValueError('compatibility.platforms 必须是非空列表')
    for platform in platforms:
        if not isinstance(platform, dict) or any(not isinstance(platform.get(k), str) or not platform[k]
                                                 for k in ('os', 'version', 'python')):
            raise ValueError('compatibility.platforms 每项必须声明 os/version/python')
        try:
            SpecifierSet(platform['python'])
        except InvalidSpecifier as error:
            raise ValueError('compatibility.platforms.python 版本范围无效') from error
        if platform.get('ros') not in {None, 'humble', 'jazzy'}:
            raise ValueError('compatibility.platforms.ros 仅支持 humble/jazzy/null')
    cuda = value.get('cuda')
    if not isinstance(cuda, dict) or not isinstance(cuda.get('required'), bool):
        raise ValueError('compatibility.cuda 必须声明 required 布尔值')
    if not isinstance(cuda.get('versions'), list) or any(not isinstance(v, str) for v in cuda['versions']):
        raise ValueError('compatibility.cuda.versions 必须是字符串列表')
    for key in ('frameworks',):
        if not isinstance(value.get(key), dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                     for k, v in value[key].items()):
            raise ValueError(f'compatibility.{key} 必须为字符串映射')
    if not isinstance(value.get('simulators'), list) or any(not isinstance(v, str) for v in value['simulators']):
        raise ValueError('compatibility.simulators 必须是字符串列表')


def profile_compatible(record, profile):
    declaration = record.get('compatibility')
    if not declaration:
        return None, '旧模板未声明结构化兼容矩阵；请维护者补充，不能据此保证兼容'
    matched = any(p['os'] == 'ubuntu' and p['version'] == profile.ubuntu
                  and p.get('ros') in {None, profile.ros}
                  and Version(profile.python) in SpecifierSet(p['python']) for p in declaration['platforms'])
    cuda = declaration['cuda']
    if cuda['required'] and (not profile.gpu or profile.cuda not in cuda['versions']):
        matched = False
    if profile.gpu and 'torch' in declaration['frameworks']:
        try:
            matched = matched and Version(profile.torch) in SpecifierSet(declaration['frameworks']['torch'])
        except (InvalidSpecifier, TypeError):
            matched = False
    return matched, f"{record['name']}@{record['version']}：" + ('匹配所选环境配置' if matched else '不支持所选环境配置')
