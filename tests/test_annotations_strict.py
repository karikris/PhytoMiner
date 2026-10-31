import pytest
import polars as pl
from phytominer import join_annotations, AnnotationError
from test_derived import parent

def test_annotation_validation_and_trim(tmp_path):
    d=parent(tmp_path/'data','a');f=tmp_path/'a.tsv'
    f.write_text('organism_id\tgene_name\tx\n1\t a \tX\n')
    with pytest.raises(AnnotationError):join_annotations(d,f)
    assert join_annotations(d,f,whitespace='trim').collect()['annotation_match'].to_list()==[True]
    f.write_text('organism_id\tgene_name\tannotation_match\n1\ta\tX\n')
    with pytest.raises(AnnotationError,match='Reserved'):join_annotations(d,f)
    f.write_text('organism_id\tother\n1\ta\n')
    with pytest.raises(AnnotationError,match='Missing'):join_annotations(d,f)
    pl.DataFrame({'organism_id':[1],'gene_name':['a']}).write_parquet(tmp_path/'n.parquet')
    with pytest.raises(AnnotationError,match='strings'):join_annotations(d,tmp_path/'n.parquet')
