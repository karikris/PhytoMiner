import subprocess
import sys
from pathlib import Path

def test_lightweight_import():
    subprocess.run([sys.executable, "-c", "import phytominer, sys; assert not {'polars', 'duckdb', 'pyarrow'} & sys.modules.keys()"], check=True)

def test_removed_modules():
    root = Path(__file__).resolve().parents[1] / "phytominer"
    for name in ["api", "data", "processing", "workflow", "utils"]:
        assert not (root / (name + ".py")).exists()
