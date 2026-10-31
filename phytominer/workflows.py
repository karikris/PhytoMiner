"""BioMart-only scientific workflows; persisted evidence precedes summaries."""
from dataclasses import asdict
from pathlib import Path
from contextlib import contextmanager
import os
import json
lazy import polars as pl
lazy import pyarrow.parquet as pq
from .models import Seed, TABLES, FEATURE_ATTRIBUTES, ValidationError, ServiceError
from .biomart import BioMartClient
from .storage import RequestCache, digest
from .dataset import DatasetWriter, HomologDataset

@contextmanager
def _run_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / '.writer.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValidationError('Dataset has an active writer; after a crash remove .writer.lock only after confirming the writer stopped') from exc
    try:
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)

def _empty(columns):
    return pl.LazyFrame(schema={c: pl.Int64 if c == 'depth' else pl.String for c in columns})

def _raw(client, cache, jobs):
    paths = []
    def execute(job):
        page, genes, organism = job
        return cache.fetch(client, page, genes, organism)
    for result in client.map(execute, jobs):
        paths.extend(result)
    return pl.scan_parquet(sorted(set(paths))) if paths else None

def _jobs(keys, batch_size):
    groups = {}
    for organism, gene in keys:
        groups.setdefault(organism, set()).add(gene)
    for organism, genes in sorted(groups.items()):
        genes = sorted(genes)
        for start in range(0, len(genes), batch_size):
            yield 'orthologs', genes[start:start+batch_size], organism

def _resolve(client, cache, raw, scratch):
    if raw.limit(1).collect().is_empty():
        return _empty(TABLES['relationships']), _empty(TABLES['features'])
    source = raw.select(pl.col('ortholog__dm_gene_name').alias('gene_name'), pl.col('ortholog__dm_organism_name').alias('organism_name'))
    target = raw.select(pl.col('ortholog__dm_ortholog_gene_name').alias('gene_name'), pl.col('ortholog__dm_ortholog_organism_name').alias('organism_name'))
    refs = pl.concat([source, target]).unique()
    gene_file = scratch / 'resolve-ids.parquet'
    refs.select('gene_name').unique().sort('gene_name').sink_parquet(gene_file)
    def jobs():
        for batch in pq.ParquetFile(gene_file).iter_batches(batch_size=client.config.batch_size):
            yield 'resolve', batch.column(0).to_pylist(), None
    features = _raw(client, cache, jobs())
    if features is None:
        raise ServiceError('Could not resolve reported gene identities')
    features = features.rename(dict(zip(FEATURE_ATTRIBUTES, TABLES['features'])))
    features = features.join(refs, on=['gene_name','organism_name'], how='semi').unique()
    identities = features.select('organism_name','gene_name','organism_id').unique()
    if identities.group_by('organism_name','gene_name').len().filter(pl.col('len')>1).limit(1).collect().height:
        raise ServiceError('Ambiguous organism/gene identity in BioMart features')
    if refs.join(identities, on=['organism_name','gene_name'], how='anti').limit(1).collect().height:
        raise ServiceError('Reported homolog identifiers could not be resolved through BioMart features')
    edges = raw.rename(dict(zip(raw.collect_schema().names(),
        ['ortholog_group','source_gene_name','source_organism_name','target_gene_name','target_organism_name','relationship'])))
    for side in ('source','target'):
        lookup = identities.rename({'organism_name':side+'_organism_name','gene_name':side+'_gene_name','organism_id':side+'_organism_id'})
        edges = edges.join(lookup, on=[side+'_organism_name',side+'_gene_name'], how='left', validate='m:1')
    return edges.select(TABLES['relationships']).unique(), features

def fetch_homologs(seeds, *, target_organisms=None, expansion_depth=0, output_dir, client=None, refresh=False):
    """Retrieve reported seed relationships; labels never multiply edge evidence."""
    seeds = sorted(set(seed if isinstance(seed, Seed) else Seed(**seed) for seed in seeds),
                   key=lambda s:(s.organism_id,s.gene_name,s.label or ''))
    if not seeds:
        raise ValidationError('At least one seed is required')
    if expansion_depth != 0:
        raise ValidationError('Expansion is not available in this milestone')
    root = Path(output_dir)
    owned = client is None
    client = client or BioMartClient()
    try:
        with _run_lock(root):
            cache = RequestCache(root / 'requests')
            fingerprint = cache.metadata(client, refresh)
            if refresh:
                # Refresh is scoped by a new metadata snapshot and bypasses request reuse.
                cache = RequestCache(root / 'refresh' / __import__('uuid').uuid4().hex)
            identity = digest({'seeds':[asdict(s) for s in seeds], 'targets':sorted(target_organisms or []),
                'depth':expansion_depth, 'metadata':fingerprint, 'endpoint':client.config.endpoint})
            if not refresh:
                try:
                    result = HomologDataset(root)
                    if result.manifest['identity'] == identity:
                        return result
                except Exception as exc:
                    from .models import IncompleteDatasetError
                    if not isinstance(exc, IncompleteDatasetError): raise
            writer = DatasetWriter(root, identity)
            seed_frame = pl.LazyFrame([asdict(s) for s in seeds], schema={c:pl.String for c in TABLES['seeds']})
            writer.write('seeds', seed_frame)
            raw = _raw(client,cache,_jobs(((s.organism_id,s.gene_name) for s in seeds),client.config.batch_size))
            edges, features = _resolve(client,cache,raw,writer.directory) if raw is not None else (_empty(TABLES['relationships']),_empty(TABLES['features']))
            if target_organisms is not None:
                allowed = features.select('organism_id','organism_name').unique().filter(
                    pl.col('organism_id').is_in(target_organisms) | pl.col('organism_name').is_in(target_organisms))
                edges = edges.join(allowed.select(pl.col('organism_id').alias('target_organism_id')).unique(),on='target_organism_id',how='semi')
            roots = seed_frame.select(pl.col('organism_id').alias('source_organism_id'),pl.col('gene_name').alias('source_gene_name')).unique()
            edges = edges.join(roots,on=['source_organism_id','source_gene_name'],how='semi')
            provenance = edges.select('source_organism_id','source_gene_name','target_organism_id','target_gene_name').unique().with_columns(
                pl.col('source_organism_id').alias('root_organism_id'),pl.col('source_gene_name').alias('root_gene_name'),pl.lit(1).alias('depth'))
            writer.write('relationships',edges.sort(TABLES['relationships']))
            writer.write('provenance',provenance.select(TABLES['provenance']).sort(TABLES['provenance']))
            genes = pl.concat([seed_frame.select('organism_id','gene_name'), edges.select(pl.col('target_organism_id').alias('organism_id'),pl.col('target_gene_name').alias('gene_name'))]).unique()
            features = features.join(genes,on=['organism_id','gene_name'],how='semi')
            writer.write('features',features.sort(TABLES['features']))
            writer.write('genes',genes.sort('organism_id','gene_name'))
            writer.write('organisms',features.select('organism_id','organism_name').unique().sort('organism_id'))
            return writer.finish(metadata_fingerprint=fingerprint, endpoint=client.config.endpoint, metrics=client.metrics)
    finally:
        if owned: client.close()
