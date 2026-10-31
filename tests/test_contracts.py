import subprocess
import sys
from pathlib import Path

def test_lightweight_import():
    subprocess.run([sys.executable, "-c", "import phytominer, sys; assert not {'polars', 'duckdb', 'pyarrow'} & sys.modules.keys()"], check=True)

def test_removed_modules():
    root = Path(__file__).resolve().parents[1] / "phytominer"
    for name in ["api", "data", "processing", "workflow", "utils"]:
        assert not (root / (name + ".py")).exists()

import pytest
from phytominer import Seed, ClientConfig, ValidationError

@pytest.mark.parametrize('org,gene', [('', 'x'), ('1', ''), ('1', 'a,b'), ('1', ' x'), (167, 'x')])
def test_seed_validation(org, gene):
    with pytest.raises(ValidationError):
        Seed(org, gene)

def test_config_and_seed():
    assert Seed('167', 'AT1G01090').label is None
    assert ClientConfig().max_workers == 2
    with pytest.raises(ValidationError):
        ClientConfig(max_workers=5)

@pytest.mark.parametrize('kwargs',[{'max_workers':1.5},{'attempts':True},{'requests_per_second':float('nan')},{'read_timeout':float('inf')}])
def test_invalid_numeric_config(kwargs):
    with pytest.raises(ValidationError): ClientConfig(**kwargs)
