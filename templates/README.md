# RDP 模板目录

所有模板统一放在 `rdk_templates/`，每个子目录自带元数据和生成资源。
RDP 每次刷新扫描 `*/template.json`，无需修改 Python 注册表；目录名用于组织文件，实际名称与版本取自元数据。
CLI、问答向导、全屏工作台使用同一份定义。

## 目录约定

以 `ros2-python/` 为例：

```text
ros2-python/
├── template.json             名称、版本、描述、别名、参数、兼容性、生成规则
├── README.md                 生成项目的说明
├── setup.py                  示例模式的项目文件
├── {{package_name}}/         路径与文件内容均支持参数替换
└── .rdp/                     RDP 控制资源，不复制到生成项目
    ├── ci.yml                --ci 对应的工作流
    ├── skeleton-ci.yml       --no-examples --ci 对应的工作流
    └── skeleton/             --no-examples 对应的文件树
```

示例模式复制模板根目录的内容，排除 `template.json`、`.rdp/`、`.git/` 和 Python 缓存。
无示例模式只复制 `generation.skeleton` 指定的文件树；未声明时生成通用空目录。
`kind` 选择通用框架适配器（`directory`、`ros2_python`、`ros2_cpp`、`ros2_bringup`、`pytorch`），
模板名称、表单、运行说明、CI 和自定义测试命令均从目录读取。新增业务模板优先用 `directory`；新增底层框架适配器才需要修改 RDP。

## 编写自己的模板

1. 新建 `rdk_templates/team-demo/`，写入下面的 `template.json`。
2. 新建 `hello.txt`，内容为 `欢迎使用 {{package_name}}`。
3. 运行 `robot-cli template list`，或在工作台按 F5；新模板会自动出现。
4. 创建项目验证效果。删除该模板目录后刷新，即可从内置列表移除。

```json
{
  "name": "team-demo",
  "version": "1.0.0",
  "description": "团队最小工程模板",
  "kind": "directory",
  "status": "published",
  "maintainer": "Team",
  "environment": ["Python >= 3.10"],
  "dependencies": [],
  "ros_distro": [],
  "changelog": ["1.0.0: 初版"],
  "aliases": ["team-starter"],
  "parameters": {
    "package_name": {
      "type": "string",
      "required": true,
      "label": "项目名称",
      "pattern": "[a-z](?:[a-z0-9_]*[a-z0-9])?"
    }
  },
  "generation": {
    "next_steps": ["cd {{project_shell}}", "cat hello.txt"]
  }
}
```

```bash
robot-cli project create team-demo --name my_demo --output ~/projects
```

`status: draft` 用于尚未评审的模板，不能直接生成；在内置目录发布由维护者评审后修改状态。
团队用户目录的模板仍通过 `template publish --reviewed-by ...` 发布。

## 可选生成规则

`template.json` 的 `generation` 支持：

| 字段 | 用途 |
| --- | --- |
| `skeleton` | 无示例模式的文件树，相对于模板目录 |
| `ci` / `skeleton_ci` | 对应模式的 CI 文件；未声明时不提供该能力 |
| `next_steps` / `skeleton_next_steps` | 生成后显示的命令或说明，不自动执行 |
| `smoke_commands` / `skeleton_smoke_commands` | 显式 `--smoke-test` 时执行的 argv 数组列表，工作目录为生成项目 |
| `smoke_engine: "ros2"` | 使用 RDP 通用 ROS 构建、解释器检查及 colcon 测试流程 |
| `ros.build_type` | ROS 标准骨架类型：`ament_python` 或 `ament_cmake` |
| `ros.node_dependency` | 示例节点使用的依赖；为 null 时不生成占位节点 |
| `ros.runtime_dependencies` | 写入 package.xml 的运行依赖 |
| `ros.example_dependencies` | 只在示例模式下写入的依赖 |
| `ros.test_dependency` | 示例模式的测试依赖 |

自定义检查和 CI 可以这样声明（需要同时提供引用的文件）：

```json
{
  "generation": {
    "skeleton": ".rdp/skeleton",
    "ci": ".rdp/ci.yml",
    "skeleton_ci": ".rdp/skeleton-ci.yml",
    "smoke_commands": [["{{python}}", "-m", "pytest", "-q"]],
    "skeleton_smoke_commands": [["{{python}}", "-c", "print('骨架检查')"]],
    "next_steps": ["cd {{project_shell}}", "python -m pytest -q"],
    "skeleton_next_steps": ["cd {{project_shell}}", "请添加自己的实现"]
  }
}
```

只声明相应模式实际可执行的检查。测试命令按 argv 执行，不隐式调用 Shell；
确实需要 Shell 时由模板作者显式声明 `bash -c`，用户只在信任模板后开启 `--smoke-test`。
导入与列表扫描不会执行模板代码。

文件路径和文本支持 `{{参数名}}`。额外变量包括 `template_id`、`template_version`、
`package_name_upper`、`language`、`python`（当前解释器）、`runner_os`（匹配 ROS 发行版的 CI 系统）、
`project_shell` 与 `workspace_shell`（已做 Shell 引号处理的绝对目录）。
参数 `label` 用于工作台与向导显示；`description` 用作输入提示。
资源路径必须位于模板内部，禁止符号链接和 `..` 越界；别名不能与其他模板或别名冲突。

## 安装与交付

模板目录独立打包为 `robot-cli-templates`，CLI 通过 `rdk_templates` 资源包读取。
在仓库根目录执行：

```bash
bash setup.sh
# 开发安装
rdk/.venv/bin/python -m pip install -e ./templates -e './rdk[dev]' wheel
rdk/.venv/bin/python -m pytest -q rdk/tests
```

开发安装后增删模板即可刷新；wheel 安装需要重新构建并安装模板包。
升级时保留旧版本目录，新建目录修改版本，同一名称和版本不能重复。
发布时构建并一同交付模板包与 CLI；CLI 声明了模板包依赖。

## 发布前整理

私有模板可暂放在统一目录，通过仓库 `.gitignore` 排除 Git 跟踪。
发布或导出环境前，由维护者把不准备交付的目录移出 `rdk_templates/`；
打包与容器导出会正常收集当时目录里的所有模板，不读取“仅限本地”标记，也不按 `.gitignore` 过滤。

版本、参数和外部模板导入命令见 [模板管理](../rdk/docs/template-management.md)。
