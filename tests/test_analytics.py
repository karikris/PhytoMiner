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

def test_duckdb_parity_and_quoted_paths(tmp_path):
    root=tmp_path / "a'quoted directory"
    dataset=fetch_homologs([Seed('1','a','X'),Seed('1','a','Y')],output_dir=root,client=FixtureClient())
    with dataset.connect() as connection:
        assert connection.sql('select count(*) from relationships').fetchall()[0][0] == dataset.scan('relationships').collect().height
        assert connection.sql('select count(distinct target_gene_name) from relationships').fetchall()[0][0] == dataset.summary().collect()['homolog_genes'].sum()
        assert connection.sql('select count(*) from features').fetchall()[0][0]==4
