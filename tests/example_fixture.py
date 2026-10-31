from test_workflows import FixtureClient
from phytominer.models import FEATURE_ATTRIBUTES, ORTHOLOG_ATTRIBUTES

class ExampleClient(FixtureClient):
    organisms={'167':'Athaliana_TAIR10','454':'Sbicolor_v3.1.1'}
    genes={'AT1G01090':'167','Sobic.006G011200':'454'}
    def metadata(self):
        ids=''.join(f'<Option value="{id}" displayName="{name}"/>' for id,name in self.organisms.items())
        names=''.join(f'<Option value="{name}" displayName="{name}"/>' for name in self.organisms.values())
        return {'fixture':'example','configuration':f'<DatasetConfig><FilterDescription internalName="organism_id">{ids}</FilterDescription><FilterDescription internalName="ortholog_organism_name">{names}</FilterDescription></DatasetConfig>'}
    def query(self,page,genes=(),organism_id=None):
        self.calls.append((page,tuple(genes),organism_id))
        if page=='orthologs':
            rows=[dict(zip(ORTHOLOG_ATTRIBUTES,['167_454_example','AT1G01090','Athaliana_TAIR10','Sobic.006G011200','Sbicolor_v3.1.1','one-to-one']))] if organism_id=='167' and 'AT1G01090' in genes else []
        else:
            rows=[dict(zip(FEATURE_ATTRIBUTES,[org,self.organisms[org],gene,org+'01',gene+'.1',org+'02'])) for gene,org in self.genes.items() if gene in genes and (organism_id is None or organism_id==org)]
        yield rows
