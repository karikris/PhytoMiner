import tempfile
from pathlib import Path
from hypothesis import given, settings, strategies as st
from phytominer import Seed,fetch_homologs
from graph_fixture import GraphClient,reference

@settings(max_examples=20,deadline=None,derandomize=True)
@given(st.lists(st.tuples(st.integers(0,3),st.integers(0,3)),max_size=12),st.sets(st.integers(0,3),min_size=1),st.sets(st.integers(0,3),min_size=1),st.sets(st.integers(0,3)),st.integers(0,3))
def test_generated_graphs(pairs,roots,allowed,missing,depth):
    edges={i:{b for a,b in pairs if a==i} for i in range(4)}
    expected,provenance=reference(edges,roots,allowed,depth,missing)
    with tempfile.TemporaryDirectory() as tmp:
        c=GraphClient(4,edges,missing)
        with fetch_homologs([Seed(str(i+1),f'g{i}') for i in roots],target_organisms=[str(i+1) for i in allowed],expansion_depth=depth,output_dir=tmp,client=c) as d:
            actual={(int(r['source_gene_name'][1:]),int(r['target_gene_name'][1:])) for r in d.scan('relationships').collect().to_dicts()}
            actual_provenance={(int(r['root_gene_name'][1:]),int(r['source_gene_name'][1:]),int(r['target_gene_name'][1:]),r['depth']) for r in d.scan('provenance').collect().to_dicts()}
            assert actual==expected and actual_provenance==provenance
        calls=len(c.calls)
        with fetch_homologs([Seed(str(i+1),f'g{i}') for i in roots],target_organisms=[str(i+1) for i in sorted(allowed,reverse=True)]*2,expansion_depth=depth,output_dir=tmp,client=c):pass
        assert len(c.calls)==calls
