"""从 checkpoint 恢复模型，在固定评测集上重新计算指标。"""
import argparse
import json
from pathlib import Path

import torch
from .data import make_datasets
from .model import make_model
from .trainer import evaluate


def main():
    parser = argparse.ArgumentParser(description='Evaluate a CPU checkpoint')
    parser.add_argument('--checkpoint', default='outputs/checkpoint.pt')
    args = parser.parse_args()
    torch.set_num_threads(1)
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    model = make_model(checkpoint['config'])
    model.load_state_dict(checkpoint['model'])
    _, test_data = make_datasets(checkpoint['config'])
    metrics = evaluate(model, test_data)
    destination = Path(args.checkpoint).parent / 'evaluation.json'
    destination.write_text(json.dumps(metrics, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
