# rdk 目录结构

```text
rdk/
├── docs/                         使用与验收文档
├── rdk_cli/
│   ├── main.py                   命令、终端向导、渲染和项目生成
│   ├── template_store.py         版本、参数、状态、评审、Git/注册表导入
│   ├── registry.py               旧登记表导入兼容入口
│   └── environment.py            ROS 生成所需 Ubuntu/Jazzy 检查
├── templates/                    以 rdk_templates 包随 wheel 分发
│   ├── ros2-python/              Python 节点、参数、Launch、pytest
│   ├── ros2-cpp/                 C++17 节点、参数、Launch、gtest
│   ├── ros2-bringup/             多节点启动、机器人配置与测试
│   └── pytorch-training/         合成 Dataset、模型、训练、评测与测试
├── tests/
│   ├── test_cli.py               命令和 ROS 环境检查
│   ├── test_templates.py         生命周期、版本、参数、导入、向导
│   ├── test_packaging.py         wheel 安装后的资源定位与生成
│   └── test_smoke.py             真实 ROS 构建运行与 CPU 训练评测
└── pyproject.toml                v1.1.0 打包配置与入口
```

每个模板的 `template.json` 是元数据和参数定义的唯一来源。
ROS 项目先由 `ros2 pkg create` 创建标准骨架，再叠加模板内容；PyTorch 与通用目录模板直接复制渲染。
替换文件路径与内容的参数占位符后，写入 `.robot-cli.json` 记录确切版本和参数。
生成的项目不导入 `rdk_cli`，也不读取原始模板路径，可脱离本仓库单独构建和运行。

仓库根目录 `.github/workflows/templates.yml` 包含 CLI/wheel、CPU PyTorch 和 ROS Jazzy 的自动化验证。
团队模板存储在用户数据目录，独立于源码仓库；使用方式见 `template-management.md`。
