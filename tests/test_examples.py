import runpy
from example_fixture import ExampleClient

def test_executable_example(tmp_path):
    run=runpy.run_path('examples/workflow.py')['run']
    dataset,counts,total=run(tmp_path,client=ExampleClient())
    assert total==dataset.scan('relationships').collect().height==1
    row=dataset.scan('relationships').collect().to_dicts()[0]
    assert (row['source_gene_name'],row['target_gene_name'])==('AT1G01090','Sobic.006G011200')
    assert counts['reported_edges'].sum()==total

def test_readme_python_examples(tmp_path,monkeypatch):
    import re
    from pathlib import Path
    import phytominer
    root=Path(__file__).resolve().parents[1]
    source=(root/'README.md').read_text()
    homologs=phytominer.fetch_homologs
    features=phytominer.fetch_features
    monkeypatch.setattr(phytominer,'fetch_homologs',lambda *a,**kw:homologs(*a,**kw,client=ExampleClient()))
    monkeypatch.setattr(phytominer,'fetch_features',lambda *a,**kw:features(*a,**kw,client=ExampleClient()))
    monkeypatch.chdir(tmp_path)
    Path('annotations.tsv').write_text('organism_id\tgene_name\tlabel\n167\tAT1G01090\tNDHA\n')
    namespace={}
    for block in re.findall(r'```python\n(.*?)```',source,re.S):
        exec(compile(block,'README.md','exec'),namespace)

    assert namespace["rows"] == [(1,)]
    assert namespace["relationships"].collect().height == 1
