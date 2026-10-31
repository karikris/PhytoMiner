"""Install the built wheel outside the repository and check public imports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

version=tomllib.loads(Path('pyproject.toml').read_text())['project']['version']
wheel=Path('dist') / f'phytominer-{version}-py3-none-any.whl'
with tempfile.TemporaryDirectory() as tmp:
    env=Path(tmp)/'venv'
    subprocess.run(['uv','venv','--python',sys.executable,str(env)],check=True)
    python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    subprocess.run(['uv','pip','install','--python',str(python),str(wheel.resolve())],check=True)
    code=f"""
import sys
import phytominer
assert phytominer.__version__ == {version!r}
assert not {{'polars','duckdb','pyarrow','requests'}} & sys.modules.keys()
from phytominer import Seed, BioMartClient, HomologDataset, fetch_homologs, fetch_features, join_annotations
Seed('167','AT1G01090')
for name in ('homologs_pipe','genes_pipe','join_tsvs'):
    assert not hasattr(phytominer,name)
print('Installed wheel API and lazy imports verified')
"""
    subprocess.run([str(python),'-I','-c',code],cwd=tmp,check=True)
