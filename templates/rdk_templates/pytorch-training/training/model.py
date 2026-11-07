"""小型多层感知机，输入特征，输出两类 logits。"""
from torch import nn


def make_model(config):
    return nn.Sequential(
        nn.Linear(config['input_dim'], config['hidden_dim']),
        nn.ReLU(),
        nn.Linear(config['hidden_dim'], 2),
    )
