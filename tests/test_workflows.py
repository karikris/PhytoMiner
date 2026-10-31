import pytest
from phytominer import Seed, fetch_homologs
from phytominer.biomart import BioMartClient
from phytominer.models import FEATURE_ATTRIBUTES, ORTHOLOG_ATTRIBUTES

class FixtureClient(BioMartClient):
    def __init__(self,config=None):
        super().__init__(config); self.calls=[]
    def metadata(self):
        organisms=[('1','org1'),('2','org2'),('167','org167'),('454','Sbicolor_v3.1.1')]
        config='<DatasetConfig><FilterDescription internalName="organism_id">'+''.join(f'<Option value="{id}" displayName="{name}"/>' for id,name in organisms)+'</FilterDescription><FilterDescription internalName="ortholog_organism_name">'+''.join(f'<Option value="{name}" displayName="{name}"/>' for id,name in organisms)+'</FilterDescription></DatasetConfig>'
        return {'fixture':'v1','configuration':config}
    def validate_metadata(self,data): pass
    def query(self,page,genes=(),organism_id=None):
        self.calls.append((page,tuple(genes),organism_id))
        if page=='orthologs':
            values=[]
            for gene in genes:
                if gene=='missing': continue
                target='b' if organism_id=='1' else 'a'
                values.extend([['g',gene,'org'+organism_id,target,'org2' if organism_id=='1' else 'org1','new-relationship']]*2)
            yield [dict(zip(ORTHOLOG_ATTRIBUTES,row)) for row in values]
        else:
            yield [dict(zip(FEATURE_ATTRIBUTES,[org,'org'+org,gene,org+gene,gene+'.'+t,org+gene+t]))
                for org in ('1','2') for gene in genes for t in ('1','2')]

def test_direct_and_offline_resume(tmp_path):
    c=FixtureClient()
    result=fetch_homologs([Seed('1','a','X'),Seed('1','a','Y')],output_dir=tmp_path,client=c)
    assert result.scan('relationships').collect().height==1
    assert result.scan('features').collect().height==4
    assert result.scan('seeds').collect().height==2
    assert result.scan('provenance').collect()['depth'].to_list()==[1]
    count=len(c.calls)
    fetch_homologs([Seed('1','a','X'),Seed('1','a','Y')],output_dir=tmp_path,client=c)
    assert len(c.calls)==count

def test_missing_genes_and_targets(tmp_path):
    result=fetch_homologs([Seed('1','missing')],output_dir=tmp_path,client=FixtureClient())
    assert result.scan('relationships').collect().is_empty()
    result=fetch_homologs([Seed('1','a')],target_organisms=['1'],output_dir=tmp_path,client=FixtureClient())
    assert result.scan('relationships').collect().is_empty()

def test_expansion_cycles_and_query_once(tmp_path):
    c=FixtureClient()
    result=fetch_homologs([Seed('1','a')],target_organisms=['1','2'],expansion_depth=5,output_dir=tmp_path,client=c)
    assert result.scan('relationships').collect().height==2
    assert sorted(result.scan('provenance').collect()['depth'].to_list())==[1,2]
    assert len([x for x in c.calls if x[0]=='orthologs'])==2
    with pytest.raises(Exception,match='boundary'):
        fetch_homologs([Seed('1','a')],expansion_depth=1,output_dir=tmp_path,client=c)

def test_expansion_multiple_roots_and_boundary(tmp_path):
    c=FixtureClient()
    result=fetch_homologs([Seed('1','a'),Seed('2','b')],target_organisms=['2'],expansion_depth=2,output_dir=tmp_path,client=c)
    rows=result.scan('relationships').collect().to_dicts()
    assert all(r['target_organism_id']=='2' for r in rows)
from phytominer import fetch_features, join_annotations

def test_feature_retrieval_and_annotations(tmp_path):
    dataset=fetch_features([Seed('1','a'),Seed('2','a')],output_dir=tmp_path/'features',client=FixtureClient())
    assert dataset.scan('features').collect().height==4
    annotation=tmp_path/'annotation.tsv'
    annotation.write_text('organism_id\tgene_name\tsubunit\n1\ta\tX\n')
    rows=join_annotations(dataset,annotation).sort('organism_id').collect()
    assert rows['annotation_match'].to_list()==[True,False]
    annotated=join_annotations(dataset,annotation,output_dir=tmp_path/'annotated')
    assert annotated.scan('annotations').collect().height==1
    annotation.write_text('organism_id\tgene_name\tsubunit\n1\ta\tX\n1\ta\tY\n')
    with pytest.raises(Exception,match='unique'): join_annotations(dataset,annotation)

def test_unresolved_targets_preserve_reported_evidence(tmp_path):
    class Stale(FixtureClient):
        def query(self,page,genes=(),organism_id=None):
            for batch in super().query(page,genes,organism_id):
                if page != 'orthologs':
                    batch=[row for row in batch if row['organism_name']!='org2']
                yield batch
    result=fetch_homologs([Seed('1','a')],target_organisms=['org2'],expansion_depth=2,output_dir=tmp_path,client=Stale())
    edge=result.scan('relationships').collect().to_dicts()[0]
    assert edge['target_organism_name']=='org2' and edge['target_organism_id'] is None
    assert result.manifest['unresolved_identity_rows']==1
    assert result.scan('provenance').collect().height==1

@pytest.mark.parametrize('workers',[1,2,4])
def test_deterministic_workers(tmp_path,workers):
    from phytominer import ClientConfig
    result=fetch_homologs([Seed('1','a'),Seed('2','b')],target_organisms=['1','2'],expansion_depth=4,output_dir=tmp_path,client=FixtureClient(ClientConfig(max_workers=workers)))
    edges=result.scan('relationships').collect()
    assert edges['source_organism_id'].to_list()==['1','2']
    assert result.scan('provenance').collect().height==4
