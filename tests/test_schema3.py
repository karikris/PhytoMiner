import pytest
import polars as pl
from phytominer.dataset import DatasetWriter, HomologDataset
from phytominer import IncompleteDatasetError

def test_required_kind_tables(tmp_path):
    w=DatasetWriter(tmp_path,'identity',kind='homologs')
    w.write('genes',pl.LazyFrame({'organism_id':['1'],'gene_name':['a']}))
    with pytest.raises(IncompleteDatasetError,match='required'):w.finish()

def test_duplicate_keys_rejected(tmp_path):
    w=DatasetWriter(tmp_path,'identity')
    w.write('genes',pl.LazyFrame({'organism_id':['1','1'],'gene_name':['a','a']}))
    with pytest.raises(IncompleteDatasetError,match='Duplicate'):w.finish()

def test_failed_seed_cannot_be_published(tmp_path):
    w=DatasetWriter(tmp_path,'invalid-outcome')
    w.write('seed_outcomes',pl.LazyFrame({'organism_id':['1'],'gene_name':['a'],'status':['failed'],'feature_status':['missing_feature']}))
    with pytest.raises(IncompleteDatasetError,match='outcome'):w.finish()
