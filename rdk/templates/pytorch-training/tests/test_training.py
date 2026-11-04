import json
from pathlib import Path

import pytest
import torch
from training.config import load_config
from training.data import make_datasets
from training.model import make_model
from training.trainer import Trainer, evaluate


def test_training_and_checkpoint(tmp_path):
    config = load_config(Path(__file__).resolve().parents[1] / 'configs/default.json')
    config['output_dir'] = str(tmp_path)
    metrics = Trainer(config).train()
    checkpoint = torch.load(tmp_path / 'checkpoint.pt', weights_only=True)
    model = make_model(checkpoint['config'])
    model.load_state_dict(checkpoint['model'])
    _, held_out = make_datasets(config)
    assert metrics == evaluate(model, held_out)
    assert metrics['accuracy'] >= 0.75
    assert json.loads((tmp_path / 'metrics.json').read_text()) == metrics
    assert checkpoint['epoch'] == config['epochs']


def test_data_reproducible_and_disjoint():
    config = load_config(Path(__file__).resolve().parents[1] / 'configs/default.json')
    train, test = make_datasets(config)
    again, _ = make_datasets(config)
    assert torch.equal(train.tensors[0], again.tensors[0])
    assert len(train) + len(test) == config['samples']
    assert train.tensors[0].data_ptr() != test.tensors[0].data_ptr()


def test_config_rejects_invalid_epochs(tmp_path):
    config = json.loads((Path(__file__).resolve().parents[1] / 'configs/default.json').read_text())
    config['epochs'] = 0
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='epochs'):
        load_config(path)
