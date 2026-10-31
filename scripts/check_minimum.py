"""Validate advertised direct lower bounds without changing the lockfile."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    env = Path(tmp)/'env'
    subprocess.run(['uv','venv','--python',sys.executable,str(env)],check=True)
    python = env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    subprocess.run(['uv','pip','install','--python',str(python),'--resolution','lowest-direct','.[dev]'],check=True)
    subprocess.run([str(python),'-m','pytest','-q'],check=True)
    subprocess.run([str(python),'-c','import polars,duckdb,pyarrow,requests; print(polars.__version__,duckdb.__version__,pyarrow.__version__,requests.__version__)'],check=True)
