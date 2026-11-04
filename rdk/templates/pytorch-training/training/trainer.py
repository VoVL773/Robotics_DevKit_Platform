"""CPU 全批次训练与独立评测。"""
import json
from pathlib import Path

import torch
from torch import nn

from .data import make_datasets
from .model import make_model


def evaluate(model, dataset):
    model.eval()
    inputs, labels = dataset.tensors
    with torch.no_grad():
        logits = model(inputs)
        return {
            'loss': nn.functional.cross_entropy(logits, labels).item(),
            'accuracy': (logits.argmax(dim=1) == labels).float().mean().item(),
            'samples': len(labels),
        }


class Trainer:
    def __init__(self, config):
        self.config = config
        torch.set_num_threads(1)
        torch.manual_seed(config['seed'])
        self.model = make_model(config)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=config['learning_rate'])
        self.train_data, self.test_data = make_datasets(config)

    def train(self):
        inputs, labels = self.train_data.tensors
        for epoch in range(1, self.config['epochs'] + 1):
            self.model.train()
            self.optimizer.zero_grad()
            loss = nn.functional.cross_entropy(self.model(inputs), labels)
            loss.backward()
            self.optimizer.step()
            print(f'epoch={epoch} loss={loss.item():.6f}')
        metrics = evaluate(self.model, self.test_data)
        output = Path(self.config['output_dir'])
        output.mkdir(parents=True, exist_ok=True)
        torch.save({
            'config': self.config,
            'model': self.model.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epoch': self.config['epochs'],
        }, output / 'checkpoint.pt')
        (output / 'metrics.json').write_text(json.dumps(metrics, indent=2) + '\n', encoding='utf-8')
        return metrics
