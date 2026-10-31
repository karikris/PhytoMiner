import json
from pathlib import Path
import polars as pl
import pytest
from phytominer.dataset import DatasetWriter, HomologDataset
from phytominer import IncompleteDatasetError


def publish_genes(root, gene='a'):
    writer = DatasetWriter(root, {'gene':gene})
    writer.write('genes', pl.LazyFrame({'organism_id':['1'], 'gene_name':[gene]}))
    return writer, writer.finish()


def test_private_staging_keeps_old_publication(tmp_path):
    _, old = publish_genes(tmp_path)
    before = (tmp_path/'manifest.json').read_bytes()
    replacement = DatasetWriter(tmp_path, {'gene':'b'})
    replacement.write('genes', pl.LazyFrame({'organism_id':['1'], 'gene_name':['b']}))
    assert (tmp_path/'manifest.json').read_bytes() == before
    assert HomologDataset(tmp_path).scan('genes').collect()['gene_name'].to_list() == ['a']
    staged = json.loads((replacement.directory/'manifest.json').read_text())
    assert staged['status'] == 'incomplete' and 'genes' in staged['tables']
    assert old.scan('genes').collect()['gene_name'].to_list() == ['a']


def test_first_staging_is_not_published(tmp_path):
    writer = DatasetWriter(tmp_path, {'first':True})
    assert not (tmp_path/'manifest.json').exists()
    assert (writer.directory/'manifest.json').exists()
    with pytest.raises(IncompleteDatasetError): HomologDataset(tmp_path)


def test_invalid_candidate_never_replaces_publication(tmp_path):
    publish_genes(tmp_path)
    before = (tmp_path/'manifest.json').read_bytes()
    writer = DatasetWriter(tmp_path, {'gene':'b'})
    writer.write('genes', pl.LazyFrame({'organism_id':['1'], 'gene_name':['b']}))
    writer.manifest['tables']['genes']['rows'] = 999
    with pytest.raises(IncompleteDatasetError, match='row count'):
        writer.finish()
    assert (tmp_path/'manifest.json').read_bytes() == before
    assert json.loads((writer.directory/'manifest.json').read_text())['status'] == 'incomplete'


def test_failed_pointer_switch_preserves_old_generation(tmp_path, monkeypatch):
    import phytominer.dataset as module
    publish_genes(tmp_path)
    before = (tmp_path/'manifest.json').read_bytes()
    writer = DatasetWriter(tmp_path, {'gene':'b'})
    writer.write('genes', pl.LazyFrame({'organism_id':['1'], 'gene_name':['b']}))
    original = module.atomic_json
    def fail_root(path, value):
        if Path(path) == tmp_path/'manifest.json': raise OSError('injected publication failure')
        return original(path, value)
    monkeypatch.setattr(module, 'atomic_json', fail_root)
    with pytest.raises(OSError, match='injected'): writer.finish()
    assert (tmp_path/'manifest.json').read_bytes() == before
    assert HomologDataset(tmp_path).scan('genes').collect()['gene_name'].to_list() == ['a']
    assert json.loads((writer.directory/'manifest.json').read_text())['status'] == 'complete'


def test_successful_switch_pins_both_readers(tmp_path):
    _, old = publish_genes(tmp_path)
    writer, new = publish_genes(tmp_path, 'b')
    assert old.scan('genes').collect()['gene_name'].to_list() == ['a']
    assert new.scan('genes').collect()['gene_name'].to_list() == ['b']
    assert HomologDataset(tmp_path).manifest == new.manifest
    assert json.loads((writer.directory/'manifest.json').read_text()) == new.manifest
