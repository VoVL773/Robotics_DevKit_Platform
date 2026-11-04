"""JSON 配置读取与校验。"""
import json
from pathlib import Path
import math


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    expected = {'seed', 'samples', 'input_dim', 'hidden_dim', 'epochs', 'learning_rate', 'output_dir'}
    if set(config) != expected:
        raise ValueError(f'config keys must be {sorted(expected)}')
    for key in ('seed', 'samples', 'input_dim', 'hidden_dim', 'epochs'):
        value = config[key]
        minimum = 0 if key == 'seed' else (8 if key == 'samples' else 1)
        if type(value) is not int or value < minimum:
            raise ValueError(f'{key} must be an integer >= {minimum}')
    rate = config['learning_rate']
    if type(rate) not in (int, float) or not math.isfinite(rate) or rate <= 0:
        raise ValueError('learning_rate must be finite and positive')
    if not isinstance(config['output_dir'], str) or not config['output_dir'].strip():
        raise ValueError('output_dir must be a non-empty path')
    return config
