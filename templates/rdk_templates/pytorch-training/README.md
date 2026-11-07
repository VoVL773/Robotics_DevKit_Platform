# {{package_name}}

独立 CPU PyTorch 二分类示例，由 {{template_id}}@{{template_version}} 生成。
维护者：{{maintainer}}。无需 ROS、GPU 或原模板仓库；数据由固定随机种子生成，无需下载。

## 安装、训练和评测

需要 Python >= 3.10。首次安装需要从 Python 包源下载 PyTorch。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m training.train --config configs/default.json
python -m training.evaluate --checkpoint outputs/checkpoint.pt
python -m pytest -q
```

`configs/default.json` 定义种子、样本数、输入维度、隐藏层、轮数、学习率和输出目录。
相对路径按当前工作目录解释。默认 256 条合成数据按 80%/20% 划分训练集与评测集，
标签由特征之和的正负确定；小型 MLP 全批次训练 20 轮。

- `training/data.py`：TensorDataset 数据生成与划分。
- `training/model.py`：输入特征到两类 logits 的模型。
- `training/trainer.py`：训练循环、评测、checkpoint 保存。
- `training/train.py`、`training/evaluate.py`：独立命令入口。
- `outputs/checkpoint.pt`：配置、模型权重、优化器状态和已训练轮数。
- `outputs/metrics.json`、`outputs/evaluation.json`：loss、accuracy、评测样本数。

指标用于验证工程流程，不代表真实机器人任务精度。只加载可信来源的 checkpoint。
