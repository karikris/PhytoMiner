from phytominer import fetch_homologs, Seed
from test_workflows import FixtureClient
import polars as pl

def test_lazy_summary_preserves_scientific_grain(tmp_path):
    dataset=fetch_homologs([Seed('1','a','X'),Seed('1','a','Y')],output_dir=tmp_path,client=FixtureClient())
    summary=dataset.summary()
    assert isinstance(summary,pl.LazyFrame)
    row=summary.collect().to_dicts()[0]
    assert row['reported_edges']==row['homolog_genes']==row['query_genes']==1
    assert row['relationship']=='new-relationship'
