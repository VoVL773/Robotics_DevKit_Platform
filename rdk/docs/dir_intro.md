# rdk 目录结构

```text
rdk/
├── .venv/                 Python 虚拟环境（不提交到 git）
├── docs/                  文档目录
│   ├── dir_intro.md       本文件：目录结构说明
│   └── quickstart.md      快速上手：创建、编译、运行示例包
├── rdk_cli/               命令行工具源码
│   ├── __init__.py        标记 rdk_cli 为可导入的包
│   ├── registry.py        模板登记表：模板名、版本、兼容的 ROS 2 发行版、语言
│   └── main.py            命令行入口：template list / template info / project create
├── templates/             模板内容，每个模板一个同名子目录
│   ├── ros2-python/       Python 模板：目录名和文件内容里的 {{package_name}} 会在生成时替换成包名
│   ├── ros2-cpp/          C++ 模板（占位，尚未实现）
│   └── pytorch-training/  PyTorch 训练模板（占位，尚未实现）
├── tests/                 pytest 测试
└── pyproject.toml         打包配置、依赖、robot-cli 命令入口
```

## 命令与代码的对应关系

| 命令 | 函数 | 文件 |
| --- | --- | --- |
| `robot-cli template list` | `template_list` | `rdk_cli/main.py` |
| `robot-cli template info NAME` | `template_info` | `rdk_cli/main.py` |
| `robot-cli project create TEMPLATE` | `project_create` | `rdk_cli/main.py` |

## 模板是怎么工作的

1. `registry.py` 的 `TEMPLATES` 登记模板元信息，`template list` / `template info` 直接读它。
2. `project create` 先调用系统里的 `ros2 pkg create` 生成标准软件包骨架。
3. 再把 `templates/<模板名>/` 下的文件复制进新项目，目录名和文件内容中的
   `{{package_name}}` 替换成 `--name` 传入的包名。

所以想加一个新模板，只要：在 `registry.py` 登记 → 在 `templates/` 下建同名目录放文件。
