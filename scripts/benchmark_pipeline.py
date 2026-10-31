"""Full offline XML-to-analytics benchmark; no remote throughput inference."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from graph_fixture import GraphClient, reference
from phytominer import Seed,fetch_homologs,HomologDataset
from phytominer.models import ORTHOLOG_ATTRIBUTES,FEATURE_ATTRIBUTES
from phytominer.storage import digest

class ParsedClient(GraphClient):
    parse_seconds=0.0
    def query(self,page,genes=(),organism_id=None):
        columns=ORTHOLOG_ATTRIBUTES if page=='orthologs' else FEATURE_ATTRIBUTES
        for batch in super().query(page,genes,organism_id):
            lines=['\t'.join(row.get(c) or '' for c in columns) for row in batch]+['[success]']
            start=time.perf_counter()
            yield from self.parse_lines(iter(lines),columns)
            self.parse_seconds+=time.perf_counter()-start
            self.metrics.append({'rows':len(batch),'response_bytes':sum(len(s.encode())+1 for s in lines),'complete':True,
                                 'query_hash':digest([page,list(genes),organism_id])})

def run_pipeline(nodes=12,fanout=2,missing_every=0):
    edges={i:{(i+j+1)%nodes for j in range(fanout)} for i in range(nodes)}
    roots={0,min(1,nodes-1)};depth=2
    missing={i for i in range(nodes) if missing_every and i%missing_every==0}
    expected,_=reference(edges,roots,set(range(nodes)),depth,missing)
    c=ParsedClient(nodes,edges,missing);report={}
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)/'run'
        args=dict(target_organisms=[str(i+1) for i in range(nodes)],expansion_depth=depth,output_dir=root,client=c)
        seeds=[Seed(str(i+1),f'g{i}') for i in roots]
        for name,refresh in [('initial',False),('resume',False),('refresh',True)]:
            calls=len(c.calls);start=time.perf_counter()
            with fetch_homologs(seeds,refresh=refresh,**args) as d:
                assert d.scan('relationships').collect().height==len(expected)
                with d.connect() as sql:assert sql.sql('select count(*) from relationships').fetchall()==[(len(expected),)]
            records=[json.loads(p.read_text()) for p in (root/'.runs').glob('*.json')]
            latest=max(records,key=lambda r:r['started_at'])
            report[name]={'seconds':time.perf_counter()-start,'query_calls':len(c.calls)-calls,'metrics':latest['metrics']}
        assert report['resume']['query_calls']==0
        report['open_seconds']={}
        for mode in ('full','metadata'):
            start=time.perf_counter()
            with HomologDataset(root,verify=mode):pass
            report['open_seconds'][mode]=time.perf_counter()-start
        stopped=Path(tmp)/'stopped'
        def stop(e):
            if e['event']=='level_completed':raise RuntimeError('benchmark interruption')
        args['output_dir']=stopped
        try:fetch_homologs(seeds,progress=stop,**args)
        except RuntimeError:pass
        calls=len(c.calls)
        with fetch_homologs(seeds,**args) as resumed:
            assert resumed.scan('relationships').collect().height==len(expected)
        report['interrupted_resume_queries']=len(c.calls)-calls
        report['parquet_bytes']=sum(p.stat().st_size for p in root.rglob('*.parquet'))
    try:
        import resource,platform
        report['peak_process_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if platform.system()=='Darwin' else 1024)
    except ImportError:report['peak_process_rss_bytes']=None
    report.update(nodes=nodes,fanout=fanout,missing_features=len(missing),expected_relationships=len(expected),parse_seconds=c.parse_seconds,network_requests=0)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--nodes',type=int,default=12);parser.add_argument('--fanout',type=int,default=2)
    parser.add_argument("--missing-every",type=int,default=0)
    args=parser.parse_args();print(json.dumps(run_pipeline(args.nodes,args.fanout,args.missing_every),indent=2))
