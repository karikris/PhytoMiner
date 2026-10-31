"""BioMart-only scientific workflows; persisted evidence precedes summaries."""
from dataclasses import asdict
from pathlib import Path
from contextlib import contextmanager
import os
import json
lazy import polars as pl
lazy import pyarrow.parquet as pq
from .models import Seed, TABLES, FEATURE_ATTRIBUTES, ValidationError, ServiceError, IncompleteDatasetError
from .biomart import BioMartClient
from .storage import RequestCache, digest, checksum
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

def _discover(client, cache, seeds, targets, expansion_depth, scratch):
    roots = sorted({(s.organism_id,s.gene_name) for s in seeds})
    frontier = {root: {root} for root in roots}
    visited = {root: {root} for root in roots}
    queried = set()
    edge_parts, feature_parts, provenance_parts = [], [], []
    all_edges = _empty(TABLES['relationships'])
    for depth in range(1, expansion_depth + 2):
        needed = set().union(*frontier.values()) - queried
        if needed:
            raw = _raw(client,cache,_jobs(needed,client.config.batch_size))
            edges, features = _resolve(client,cache,raw,scratch) if raw is not None else (_empty(TABLES['relationships']),_empty(TABLES['features']))
            sources = pl.LazyFrame([{'source_organism_id':o,'source_gene_name':g} for o,g in sorted(needed)])
            edges = edges.join(sources,on=['source_organism_id','source_gene_name'],how='semi')
            if targets is not None:
                allowed = features.filter(pl.col('organism_id').is_in(targets) | pl.col('organism_name').is_in(targets)).select(pl.col('organism_id').alias('target_organism_id')).unique()
                edges = edges.join(allowed,on='target_organism_id',how='semi')
            edge_path = scratch / f'edges-{depth}.parquet'
            feature_path = scratch / f'features-{depth}.parquet'
            edges.sink_parquet(edge_path); features.sink_parquet(feature_path)
            edge_parts.append(edge_path); feature_parts.append(feature_path)
            all_edges = pl.scan_parquet(edge_parts).unique()
            queried.update(needed)
        front = [{'root_organism_id':r[0], 'root_gene_name':r[1], 'source_organism_id':n[0], 'source_gene_name':n[1]}
                 for r,nodes in frontier.items() for n in nodes]
        if not front:
            break
        step = all_edges.join(pl.LazyFrame(front),on=['source_organism_id','source_gene_name'],how='inner').with_columns(pl.lit(depth).alias('depth')).select(TABLES['provenance']).unique()
        path = scratch / f'provenance-{depth}.parquet'
        step.sink_parquet(path); provenance_parts.append(path)
        next_frontier = {root:set() for root in roots}
        for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
            for row in batch.to_pylist():
                root=(row['root_organism_id'],row['root_gene_name'])
                node=(row['target_organism_id'],row['target_gene_name'])
                if node not in visited[root]:
                    visited[root].add(node); next_frontier[root].add(node)
        frontier = next_frontier
        if not any(frontier.values()):
            break
    return (all_edges, pl.scan_parquet(feature_parts).unique() if feature_parts else _empty(TABLES['features']),
            pl.scan_parquet(provenance_parts).unique() if provenance_parts else _empty(TABLES['provenance']))

def fetch_homologs(seeds, *, target_organisms=None, expansion_depth=0, output_dir, client=None, refresh=False):
    """Retrieve reported seed relationships; labels never multiply edge evidence."""
    seeds = sorted(set(seed if isinstance(seed, Seed) else Seed(**seed) for seed in seeds),
                   key=lambda s:(s.organism_id,s.gene_name,s.label or ''))
    if not seeds:
        raise ValidationError('At least one seed is required')
    if not isinstance(expansion_depth, int) or isinstance(expansion_depth, bool) or expansion_depth < 0:
        raise ValidationError('Expansion depth must be a nonnegative integer')
    if expansion_depth and not target_organisms:
        raise ValidationError('Expansion requires an explicit organism boundary')
    root = Path(output_dir)
    owned = client is None
    client = client or BioMartClient()
    try:
        with _run_lock(root):
            cache = RequestCache(root / 'requests', refresh=refresh)
            fingerprint = cache.metadata(client, refresh)
            identity = digest({'seeds':[asdict(s) for s in seeds], 'targets':sorted(target_organisms or []),
                'depth':expansion_depth, 'metadata':fingerprint, 'endpoint':client.config.endpoint})
            if not refresh:
                try:
                    result = HomologDataset(root)
                    if result.manifest['identity'] == identity:
                        return result
                except IncompleteDatasetError:
                    pass
            writer = DatasetWriter(root, identity)
            seed_frame = pl.LazyFrame([asdict(s) for s in seeds], schema={c:pl.String for c in TABLES['seeds']})
            writer.write('seeds', seed_frame)
            edges, features, provenance = _discover(client, cache, seeds, target_organisms, expansion_depth, writer.directory)
            writer.write('relationships',edges.sort(TABLES['relationships']))
            writer.write('provenance',provenance.select(TABLES['provenance']).sort(TABLES['provenance']))
            genes = pl.concat([seed_frame.select('organism_id','gene_name'), edges.select(pl.col('target_organism_id').alias('organism_id'),pl.col('target_gene_name').alias('gene_name'))]).unique()
            seed_jobs=(('features',batch,org) for _,batch,org in _jobs(((s.organism_id,s.gene_name) for s in seeds),client.config.batch_size))
            seed_features=_raw(client,cache,seed_jobs)
            if seed_features is not None:
                features=pl.concat([features,seed_features.rename(dict(zip(FEATURE_ATTRIBUTES,TABLES['features'])))]).unique()
            features = features.join(genes,on=['organism_id','gene_name'],how='semi')
            writer.write('unmatched_genes',genes.join(features.select('organism_id','gene_name').unique(),on=['organism_id','gene_name'],how='anti'))
            writer.write('features',features.sort(TABLES['features']))
            writer.write('genes',genes.sort('organism_id','gene_name'))
            writer.write('organisms',features.select('organism_id','organism_name').unique().sort('organism_id'))
            return writer.finish(metadata_fingerprint=fingerprint, endpoint=client.config.endpoint, metrics=client.metrics)
    finally:
        if owned: client.close()

def fetch_features(genes, *, output_dir, client=None, refresh=False):
    """Retrieve transcript-grain features for organism-qualified genes."""
    genes = sorted({(s.organism_id,s.gene_name) for s in
                    (g if isinstance(g,Seed) else Seed(**g) for g in genes)})
    if not genes:
        raise ValidationError('At least one gene is required')
    root=Path(output_dir); owned=client is None; client=client or BioMartClient()
    try:
        with _run_lock(root):
            cache=RequestCache(root/'requests'); fingerprint=cache.metadata(client,refresh)
            identity=digest({'genes':genes,'metadata':fingerprint,'endpoint':client.config.endpoint})
            if not refresh:
                try:
                    previous=HomologDataset(root)
                    if previous.manifest['identity']==identity: return previous
                except IncompleteDatasetError:
                    pass
            writer=DatasetWriter(root,identity)
            jobs=(('features',batch,org) for _,batch,org in _jobs(genes,client.config.batch_size))
            def execute(job): return cache.fetch(client,*job,refresh=refresh)
            paths=[path for result in client.map(execute,jobs) for path in result]
            features=pl.scan_parquet(paths).rename(dict(zip(FEATURE_ATTRIBUTES,TABLES['features']))) if paths else _empty(TABLES['features'])
            wanted=pl.LazyFrame([{'organism_id':o,'gene_name':g} for o,g in genes])
            features=features.join(wanted,on=['organism_id','gene_name'],how='semi').unique()
            writer.write('genes',wanted)
            writer.write('features',features.sort(TABLES['features']))
            writer.write('organisms',features.select('organism_id','organism_name').unique().sort('organism_id'))
            writer.write('unmatched_genes',wanted.join(features.select('organism_id','gene_name').unique(),on=['organism_id','gene_name'],how='anti'))
            return writer.finish(metadata_fingerprint=fingerprint,metrics=client.metrics)
    finally:
        if owned: client.close()

def join_annotations(dataset, annotation_file, *, organism_column='organism_id', gene_column='gene_name', has_header=True, column_names=None, output_dir=None):
    """Left join unique organism/gene annotations; ambiguous keys are errors."""
    path=Path(annotation_file)
    if path.suffix=='.parquet':
        annotation=pl.scan_parquet(path)
    elif path.suffix in ('.csv','.tsv'):
        if not has_header and not column_names:
            raise ValidationError('Headerless input requires explicit column_names')
        annotation=pl.scan_csv(path,separator='\t' if path.suffix=='.tsv' else ',',has_header=has_header,
                               new_columns=column_names,infer_schema=False)
    else:
        raise ValidationError('Annotation format must be CSV, TSV or Parquet')
    keys=['organism_id','gene_name']
    annotation=annotation.rename({organism_column:'organism_id',gene_column:'gene_name'}).with_columns(pl.col(keys).cast(pl.String))
    if annotation.filter(pl.any_horizontal(pl.col(keys).is_null() | (pl.col(keys).str.strip_chars()=='') | (pl.col(keys)==''))).limit(1).collect().height:
        raise ValidationError('Annotation keys must be nonempty')
    if annotation.group_by(keys).len().filter(pl.col('len')>1).limit(1).collect().height:
        raise ValidationError('Annotation organism/gene keys must be unique')
    result=dataset.scan('genes').join(annotation.with_columns(pl.lit(True).alias('annotation_match')),on=keys,how='left',validate='m:1').with_columns(pl.col('annotation_match').fill_null(False))
    if output_dir is None:
        return result
    root=Path(output_dir)
    if root.resolve()==dataset.root.resolve():
        raise ValidationError('Use a separate output directory for annotated datasets')
    with _run_lock(root):
        writer=DatasetWriter(root,digest({'parent':dataset.manifest['identity'],'annotation':checksum(path)}))
        for table in dataset.manifest['tables']: writer.write(table,dataset.scan(table))
        writer.write('annotations',annotation)
        writer.write('annotated_genes',result)
        return writer.finish()
