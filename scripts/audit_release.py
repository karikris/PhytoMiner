"""Audit active code and the distribution for removed backend implementation."""
from pathlib import Path
import re
import tomllib
import zipfile
import tarfile
from phytominer import __version__

BANNED=re.compile(r'intermine|phytomine/|primaryIdentifier|secondaryIdentifier|organism\.shortName|homologs_pipe|genes_pipe|join_tsvs|subunit1|PHYTOZOME_SERVICE_URL|import pandas|import seaborn',re.I)
OLD={'api.py','config.py','data.py','processing.py','workflow.py','utils.py'}

def audit():
    for path in Path('phytominer').glob('*.py'):
        assert path.name not in OLD, path
        assert not BANNED.search(path.read_text()),path
    project=tomllib.loads(Path('pyproject.toml').read_text())['project']
    assert __version__=='1.0.0' and project['requires-python']=='>=3.15'
    assert not re.search(r'intermine|pandas|seaborn|matplotlib',' '.join(project['dependencies']),re.I)
    wheel=Path('dist')/f'phytominer-{__version__}-py3-none-any.whl'
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith('phytominer/') and name.endswith('.py'):
                assert Path(name).name not in OLD,name
                assert not BANNED.search(archive.read(name).decode()),name
            if name.endswith('/METADATA'):
                data=archive.read(name).decode()
                requires='\n'.join(line for line in data.splitlines() if line.startswith('Requires-Dist:'))
                assert not re.search(r'intermine|pandas|seaborn|matplotlib',requires,re.I)
    with tarfile.open(Path('dist') / f'phytominer-{__version__}.tar.gz') as archive:
        for member in archive.getmembers():
            name=member.name
            if '/phytominer/' in name and name.endswith('.py'):
                assert Path(name).name not in OLD,name
                assert not BANNED.search(archive.extractfile(member).read().decode()),name
    print('Active source and 1.0 wheel legacy-removal audit passed')

if __name__=='__main__': audit()
