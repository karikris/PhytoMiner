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
