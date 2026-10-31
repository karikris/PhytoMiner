"""Deterministic finite BioMart graph for generated tests and benchmarks."""
from test_workflows import FixtureClient
from phytominer.models import ORTHOLOG_ATTRIBUTES, FEATURE_ATTRIBUTES

class GraphClient(FixtureClient):
    def __init__(self, count, edges, missing=()):
        super().__init__();self.count=count;self.edges=edges;self.missing=set(missing)
    def metadata(self):
        ids=''.join(f'<Option value="{i+1}" displayName="org{i+1}"/>' for i in range(self.count))
        names=''.join(f'<Option value="org{i+1}" displayName="org{i+1}"/>' for i in range(self.count))
        return {'fixture':'graph','configuration':f'<DatasetConfig><FilterDescription internalName="organism_id">{ids}</FilterDescription><FilterDescription internalName="ortholog_organism_name">{names}</FilterDescription></DatasetConfig>'}
    def query(self,page,genes=(),organism_id=None):
        self.calls.append((page,tuple(genes),organism_id));rows=[]
        if page=='orthologs':
            source=int(organism_id)-1
            if f'g{source}' in genes:
                for target in sorted(self.edges.get(source,())):
                    rows.append(dict(zip(ORTHOLOG_ATTRIBUTES,[f'{source}:{target}',f'g{source}',f'org{source+1}',f'g{target}',f'org{target+1}','many-to-many'])))
        else:
            for node in range(self.count):
                if f'g{node}' in genes and node not in self.missing and (organism_id is None or organism_id==str(node+1)):
                    for transcript in range(node%3+1):
                        rows.append(dict(zip(FEATURE_ATTRIBUTES,[str(node+1),f'org{node+1}',f'g{node}',str(1000+node),f'g{node}.{transcript}',str(node*10+transcript)])))
        yield rows

def reference(edges,roots,allowed,depth,missing):
    evidence=set();provenance=set()
    for root in roots:
        frontier={root};seen={root}
        for level in range(1,depth+2):
            nxt=set()
            for source in frontier:
                for target in edges.get(source,()):
                    if target not in allowed:continue
                    evidence.add((source,target));provenance.add((root,source,target,level))
                    if target not in seen and target not in missing:seen.add(target);nxt.add(target)
            frontier=nxt
            if not frontier:break
    return evidence,provenance
