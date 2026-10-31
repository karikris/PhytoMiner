"""Public orchestration for BioMart dataset workflows."""
from dataclasses import asdict
from pathlib import Path
lazy import polars as pl
from .models import Seed, TABLES, FEATURE_ATTRIBUTES, ValidationError, IncompleteDatasetError
from .biomart import BioMartClient
from .storage import RequestCache
from .dataset import DatasetWriter, HomologDataset
from .inputs import _normalize_targets, _result_identity, _target_identity
from .lifecycle import _run_lock
from .normalization import _empty, _raw, _jobs, _resolve, _resolution_status
from .traversal import _discover
from .annotations import join_annotations

def fetch_homologs(seeds, *, target_organisms=None, expansion_depth=0, output_dir, client=None, refresh=False):
    """Retrieve reported seed relationships; labels never multiply edge evidence."""
    seeds = sorted(set(seed if isinstance(seed, Seed) else Seed(**seed) for seed in seeds),
                   key=lambda s:(s.organism_id,s.gene_name,s.label is not None,s.label or ''))
    if not seeds:
        raise ValidationError('At least one seed is required')
    if not isinstance(expansion_depth, int) or isinstance(expansion_depth, bool) or expansion_depth < 0:
        raise ValidationError('Expansion depth must be a nonnegative integer')
    target_organisms = _normalize_targets(target_organisms)
    if expansion_depth and not target_organisms:
        raise ValidationError('Expansion requires an explicit organism boundary')
    root = Path(output_dir)
    owned = client is None
    client = client or BioMartClient()
    try:
        with _run_lock(root):
            cache = RequestCache(root / 'requests', refresh=refresh)
            fingerprint = cache.metadata(client, refresh)
            identity = _result_identity('homologs', seeds=[asdict(s) for s in seeds], targets=_target_identity(target_organisms),
                depth=expansion_depth, metadata=fingerprint, endpoint=client.config.endpoint, dataset=client.config.dataset, virtual_schema=client.config.virtual_schema)
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
            if target_organisms == ():
                edges, features, provenance = (_empty(TABLES[name]) for name in ('relationships', 'features', 'provenance'))
            else:
                edges, features, provenance = _discover(client, cache, seeds, target_organisms, expansion_depth, writer.directory, raw_fetch=_raw, resolver=_resolve)
            writer.write('provenance',provenance.select(TABLES['provenance']).sort(TABLES['provenance']))
            genes = pl.concat([seed_frame.select('organism_id','gene_name'), edges.select(pl.col('target_organism_id').alias('organism_id'),pl.col('target_gene_name').alias('gene_name'))]).filter(pl.col('organism_id').is_not_null()).unique()
            seed_jobs=(('features',batch,org) for _,batch,org in _jobs(((s.organism_id,s.gene_name) for s in seeds),client.config.batch_size))
            seed_features=_raw(client,cache,seed_jobs)
            if seed_features is not None:
                features=pl.concat([features,seed_features.rename(dict(zip(FEATURE_ATTRIBUTES,TABLES['features'])))]).unique()
            features = features.join(genes,on=['organism_id','gene_name'],how='semi')
            writer.write('unmatched_genes',genes.join(features.select('organism_id','gene_name').unique(),on=['organism_id','gene_name'],how='anti'))
            edges = _resolution_status(edges, features)
            writer.write('relationships',edges.sort(TABLES['relationships']))
            writer.write('features',features.sort(TABLES['features']))
            writer.write('genes',genes.sort('organism_id','gene_name'))
            writer.write('organisms',features.select('organism_id','organism_name').unique().sort('organism_id'))
            unresolved=edges.filter((pl.col('source_resolution_status') == 'missing_feature') | (pl.col('target_resolution_status') == 'missing_feature'))
            writer.write('unresolved_relationships',unresolved)
            return writer.finish(metadata_fingerprint=fingerprint, endpoint=client.config.endpoint, metrics=client.metrics, unresolved_identity_rows=writer.manifest['tables']['unresolved_relationships']['rows'])
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
            identity=_result_identity('features', genes=genes, metadata=fingerprint, endpoint=client.config.endpoint, dataset=client.config.dataset, virtual_schema=client.config.virtual_schema)
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
