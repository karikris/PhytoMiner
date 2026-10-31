"""Deterministic synthetic Parquet/Polars/DuckDB workload; no network access."""
import argparse
import json
import platform
import tempfile
import time
from pathlib import Path
import polars as pl
from phytominer.dataset import DatasetWriter


def run(rows, scenario="low"):
    if scenario not in ("low","high"): raise ValueError("Unknown scenario")
    start=time.perf_counter()
    frame=pl.LazyFrame().select(pl.int_range(0,rows).alias('n')).select(
        pl.lit('167').alias('source_organism_id'),pl.lit('TAIR10').alias('source_organism_name'),
        (pl.lit('seed_')+(pl.col('n')%100).cast(pl.String)).alias('source_gene_name'),
        ((pl.col('n')%100+1).cast(pl.String) if scenario=='high' else pl.lit('454')).alias('target_organism_id'),
        ((pl.lit('organism_')+(pl.col('n')%100).cast(pl.String)) if scenario=='high' else pl.lit('Sbicolor_v3.1.1')).alias('target_organism_name'),
        (pl.lit('gene_')+pl.col('n').cast(pl.String)).alias('target_gene_name'),
        (pl.lit('group_')+(pl.col('n') if scenario=='high' else pl.col('n')%100).cast(pl.String)).alias('ortholog_group'),
        (pl.when(pl.col('n')%2==0).then(pl.lit('one-to-one')).otherwise(pl.lit('many-to-many')) if scenario=='high' else pl.lit('one-to-one')).alias('relationship'),
        pl.lit('resolved').alias('source_resolution_status'),
        pl.lit('resolved').alias('target_resolution_status'))
    with tempfile.TemporaryDirectory() as tmp:
        writer=DatasetWriter(tmp,{'benchmark_rows':rows})
        writer.write('relationships',frame)
        dataset=writer.finish()
        summary=dataset.summary().collect()
        with dataset.connect() as connection:
            sql=connection.sql('select count(*),count(distinct target_gene_name) from relationships').fetchall()[0]
        assert sql==(rows,rows)
        assert summary['reported_edges'].sum()==rows
        size=sum(p.stat().st_size for p in Path(tmp).rglob('*.parquet'))
        dataset.close()
    peak=None
    try:
        import resource
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system()!='Darwin': peak*=1024
    except ImportError:
        pass
    return {'rows':rows,'scenario':scenario,'elapsed_seconds':time.perf_counter()-start,'parquet_bytes':size,
            'peak_process_rss_bytes':peak,'network_requests':0,'sql_polars_match':True,
            'platform':platform.platform(),'python':platform.python_version()}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--rows',type=int,default=1000000)
    parser.add_argument('--scenario',choices=['low','high'],default='low')
    args=parser.parse_args()
    print(json.dumps(run(args.rows,args.scenario),indent=2))
