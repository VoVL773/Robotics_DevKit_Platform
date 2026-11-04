"""固定种子的合成二分类数据，无需下载；保留独立评测集。"""
import torch
from torch.utils.data import TensorDataset


def make_datasets(config):
    generator = torch.Generator().manual_seed(config['seed'])
    inputs = torch.randn(config['samples'], config['input_dim'], generator=generator)
    labels = (inputs.sum(dim=1) > 0).long()
    split = int(config['samples'] * 0.8)
    return (TensorDataset(inputs[:split], labels[:split]),
            TensorDataset(inputs[split:], labels[split:]))
