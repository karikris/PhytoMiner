import polars as pl
from phytominer.dataset import DatasetWriter
from phytominer import join_annotations

def parent(path,gene):
    w=DatasetWriter(path,'same-query')
    w.write('genes',pl.LazyFrame({'organism_id':['1'],'gene_name':[gene]}))
    return w.finish()

def test_derived_content_and_interpretation_identity(tmp_path):
    a=parent(tmp_path/'a','a'); b=parent(tmp_path/'b','b')
    tsv=tmp_path/'ann.tsv';tsv.write_text('organism_id\tgene_name\tx\n1\ta\tX\n')
    x=join_annotations(a,tsv,output_dir=tmp_path/'x')
    y=join_annotations(b,tsv,output_dir=tmp_path/'y')
    z=join_annotations(a,tsv,organism_column='gene_name',gene_column='organism_id',output_dir=tmp_path/'z')
    same=join_annotations(a,tsv,output_dir=tmp_path/'same')
    assert len({x.manifest['identity'],y.manifest['identity'],z.manifest['identity']})==3
    assert x.manifest['identity']==same.manifest['identity']
    assert x.manifest['kind']=='annotated'
