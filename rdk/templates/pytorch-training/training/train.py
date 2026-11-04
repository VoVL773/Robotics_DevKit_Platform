"""入口：python -m training.train --config configs/default.json。"""
import argparse
import json
from .config import load_config
from .trainer import Trainer


def main():
    parser = argparse.ArgumentParser(description='Train a small CPU classifier')
    parser.add_argument('--config', default='configs/default.json')
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(Trainer(config).train(), indent=2))


if __name__ == '__main__':
    main()
