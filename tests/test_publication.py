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


def test_partial_table_write_keeps_previous_and_removes_temp(tmp_path, monkeypatch):
    publish_genes(tmp_path)
    before = (tmp_path/'manifest.json').read_bytes()
    writer = DatasetWriter(tmp_path, {'gene':'b'})
    def bad_sink(frame, path, **kwargs):
        Path(path).write_bytes(b'partial')
        raise OSError('interrupted table write')
    monkeypatch.setattr(pl.LazyFrame, 'sink_parquet', bad_sink)
    with pytest.raises(OSError):
        writer.write('genes', pl.LazyFrame({'organism_id':['1'], 'gene_name':['b']}))
    assert (tmp_path/'manifest.json').read_bytes() == before
    assert not list(writer.directory.glob('*.tmp'))


def test_first_invalid_publication_never_creates_pointer(tmp_path):
    writer = DatasetWriter(tmp_path, 'first')
    writer.write('genes', pl.LazyFrame({'organism_id':['1'], 'gene_name':['a']}))
    (writer.directory/'genes.parquet').write_bytes(b'corrupt')
    with pytest.raises(IncompleteDatasetError): writer.finish()
    assert not (tmp_path/'manifest.json').exists()
    with pytest.raises(IncompleteDatasetError): HomologDataset(tmp_path)


def test_atomic_replace_failure_cleans_temporary_pointer(tmp_path, monkeypatch):
    import phytominer.storage as storage
    publish_genes(tmp_path)
    before = (tmp_path/'manifest.json').read_bytes()
    writer = DatasetWriter(tmp_path, {'gene':'b'})
    writer.write('genes', pl.LazyFrame({'organism_id':['1'], 'gene_name':['b']}))
    replace = storage.os.replace
    def fail_pointer(src, dst):
        if Path(dst) == tmp_path/'manifest.json': raise OSError('replace failed')
        return replace(src, dst)
    monkeypatch.setattr(storage.os, 'replace', fail_pointer)
    with pytest.raises(OSError, match='replace failed'): writer.finish()
    assert (tmp_path/'manifest.json').read_bytes() == before
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('workflow', ['homologs','features','annotations'])
def test_workflow_failure_preserves_published_dataset(tmp_path, monkeypatch, workflow):
    from phytominer import Seed, fetch_homologs, fetch_features, join_annotations
    from test_workflows import FixtureClient
    output = tmp_path/'output'
    _, old = publish_genes(output)
    before = (output/'manifest.json').read_bytes()
    _, source = publish_genes(tmp_path/'source')
    annotation = tmp_path/'annotations.tsv'
    annotation.write_text('organism_id\tgene_name\tlabel\n1\ta\tX\n')
    original = DatasetWriter.write
    def fail(self, name, frame):
        if name == ('annotations' if workflow == 'annotations' else 'features'):
            raise OSError('injected workflow failure')
        return original(self, name, frame)
    monkeypatch.setattr(DatasetWriter, 'write', fail)
    with pytest.raises(OSError, match='workflow failure'):
        if workflow == 'homologs':
            fetch_homologs([Seed('1','a')], output_dir=output, client=FixtureClient())
        elif workflow == 'features':
            fetch_features([Seed('1','a')], output_dir=output, client=FixtureClient())
        else:
            join_annotations(source, annotation, output_dir=output)
    assert (output/'manifest.json').read_bytes() == before
    assert old.scan('genes').collect()['gene_name'].to_list() == ['a']
    assert HomologDataset(output).manifest == old.manifest
    assert not (output/'.writer.lock').exists()
    if workflow != 'annotations': assert list((output/'requests').glob('*.parquet'))
