# CLI v1.1 模板管理

## 版本与生命周期

模板身份为 `name@MAJOR.MINOR.PATCH`，例如 `ros2-cpp@1.0.0`。
当前支持三个非负整数的正式版本，不支持预发布标签或版本范围。
项目创建时省略版本会选择**已发布且启用的最高数字版本**；建议团队脚本固定版本。
`info`、启停和发布命令省略版本时选择最高已安装版本，包括草稿，因此管理时建议写全版本。

```bash
robot-cli template list
robot-cli template info ros2-cpp@1.0.0
robot-cli template disable ros2-cpp@1.0.0
robot-cli template enable ros2-cpp@1.0.0
```

新建和外部导入的模板均为停用草稿。发布前完成团队评审，再记录评审人：

```bash
robot-cli template create team-demo --version 1.2.0 --maintainer 'Robot Team'
# 编辑命令输出的模板目录，补充代码、文档和测试
robot-cli template publish team-demo@1.2.0 --reviewed-by 'reviewer@example.com'
```

`create` 提供 `template.json` 和 README 草稿，不会自动写出完整业务模板。
`--kind` 支持 `directory`、`ros2_python`、`ros2_cpp`、`ros2_bringup`、`pytorch`；
默认通用目录模板适合团队自定义脚手架。ROS 类型会先调用 ROS 原生工具生成骨架，再叠加模板文件。

发布会记录评审人与 UTC 时间，并启用版本。CLI 不会覆盖同名同版本，也不会再次发布已发布版本。
升级时使用新版本号。停用、导入和升级均不修改已生成项目。
每个项目的 `.robot-cli.json` 固定模板名称、版本、生成参数和来源提交。
发布门槛是评审记录，不是具备身份验证和多人审批的服务；团队仍需在 Git PR 中实际完成评审。
CLI 不阻止用户用文件编辑器手动修改本地文件，正式模板应通过受审 Git 版本维护。

## 存储与元数据

内置模板随 wheel 分发。团队模板与启停状态默认存储在
`~/.local/share/robot-cli/templates/`，可用 `ROBOT_CLI_TEMPLATE_HOME` 设置其他目录。
无需 ROS 即可查看、编辑或导入模板。

```text
templates/
├── state.json
└── team-demo/
    └── 1.2.0/
        ├── template.json
        ├── README.md
        └── ...
```

`template.json` 示例：

```json
{
  "name": "team-demo",
  "version": "1.2.0",
  "description": "团队演示工程",
  "maintainer": "Robot Team",
  "kind": "directory",
  "status": "draft",
  "environment": ["Python >= 3.10"],
  "dependencies": [],
  "ros_distro": [],
  "changelog": ["1.2.0: 增加日志模块"],
  "parameters": {
    "package_name": {
      "type": "string",
      "required": true,
      "pattern": "[a-z](?:[a-z0-9_]*[a-z0-9])?"
    },
    "device": {
      "type": "string",
      "default": "cpu",
      "enum": ["cpu", "cuda"]
    },
    "batch_size": {
      "type": "integer",
      "default": 16,
      "minimum": 1,
      "maximum": 1024
    }
  }
}
```

参数支持 string、integer、number、boolean，支持 default、required、pattern、enum、minimum、maximum。
所有模板必须声明字符串参数 `package_name`。
参数名、项目名、节点名、模板兼容发行版和未知/重复参数都会校验。
项目名采用小写字母、数字、下划线，不能以数字开头或以下划线结尾，也不能使用 Python/C++ 关键字。
ROS 生成器支持 Humble/Jazzy；元数据中的 ros_distro 必须是二者的非空子集。内置 1.0 保持 Jazzy 约束，1.1 支持双发行版。compatibility 声明 OS、ROS、Python、CUDA、框架和仿真器范围，详见 [环境管理](environments.md)。

```bash
robot-cli project create team-demo@1.2.0 --name demo \
  --param device=cpu --param batch_size=32 --output ~/projects
```

非字符串参数按 JSON 解析，例如 `--param debug=true`。
文件路径与 UTF-8 文件内容中的 `{{package_name}}`、`{{device}}` 等占位符会被替换；
二进制文件原样复制。未定义占位符、符号链接和路径越界会报错。
生成时不复制模板元数据、Git 历史或 Python 缓存，也不执行模板自带脚本。
模板内容应自包含，不引用原始模板目录；ROS、torch 等声明的运行依赖仍需安装。
`--smoke-test` 和 `--ci` 分别执行或生成内置 ROS/PyTorch 测试流程，通用 directory 模板需自行提供测试方法。

## 从内部 Git 获取模板

已有 Git 访问权限即可使用 HTTPS、SSH URL 或本地 Git 仓库；CLI 不管理凭据。
指定 ref 时会检出该引用并记录最终提交 SHA，依赖 Git 维护具体权限。

```bash
robot-cli template install ssh://git@git.example.com/robot/templates.git \
  --ref v1.2.0 --subdir templates/team-demo
robot-cli template info team-demo@1.2.0
robot-cli template publish team-demo@1.2.0 --reviewed-by 'reviewer@example.com'
```

也支持不经 Git 导入本地模板目录：

```bash
robot-cli template install /absolute/path/to/team-demo
```

导入文件必须包含有效的 `template.json`。远端标记为 published 的模板也会在本地重置为停用草稿，
重新记录本地评审后启用。CLI 不执行 Git 子模块或模板安装钩子。

## 从注册表获取模板

首期注册表采用 JSON 索引，可以是本地文件或 HTTP(S) URL，无需部署专用注册表服务。
条目指向 Git 仓库、版本引用和模板子目录：

```json
{
  "templates": {
    "team-demo@1.2.0": {
      "git": "ssh://git@git.example.com/robot/templates.git",
      "ref": "v1.2.0",
      "subdir": "templates/team-demo"
    }
  }
}
```

```bash
robot-cli template install team-demo@1.2.0 \
  --registry https://registry.example.com/templates.json
```

CLI 校验注册表引用与下载的模板名称、版本一致。
本地注册表的 `git` 路径建议使用绝对路径；相对路径按命令当前工作目录解释。
HTTP 注册表目前不提供专门的认证参数；内部访问通过网络环境和 Git 自身认证配置解决。
