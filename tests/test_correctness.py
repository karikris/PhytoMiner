import pytest
from phytominer import Seed, fetch_homologs, ValidationError
from phytominer.workflows import _normalize_targets
from test_workflows import FixtureClient


def test_target_normalization_consumes_once():
    def values():
        yield '2'
        yield '1'
        yield '2'
    assert _normalize_targets(values()) == ('1', '2')
    assert _normalize_targets(None) is None
    assert _normalize_targets([]) == ()


@pytest.mark.parametrize('value', ['12', b'12', 12, [''], [' 1'], [1], [None]])
def test_invalid_targets(value):
    with pytest.raises(ValidationError):
        _normalize_targets(value)


def test_empty_targets_skip_ortholog_requests(tmp_path):
    client = FixtureClient()
    result = fetch_homologs([Seed('1', 'a')], target_organisms=[], output_dir=tmp_path, client=client)
    assert result.scan('relationships').collect().is_empty()
    assert result.scan('features').collect().height == 2
    assert all(page != 'orthologs' for page, _, _ in client.calls)


def test_generator_targets_match_list(tmp_path):
    client = FixtureClient()
    result = fetch_homologs([Seed('1', 'a')], target_organisms=(v for v in ['2', '2']), output_dir=tmp_path, client=client)
    assert result.scan('relationships').collect().height == 1

@pytest.mark.parametrize('selections', [(None, []), ([], None)])
def test_selection_identity_both_request_orders(tmp_path, selections):
    client = FixtureClient()
    results = [fetch_homologs([Seed('1', 'a')], target_organisms=targets, output_dir=tmp_path, client=client) for targets in selections]
    assert results[0].manifest['identity'] != results[1].manifest['identity']
    assert [d.scan('relationships').collect().height for d in results] == [1 if v is None else 0 for v in selections]


def test_equivalent_selections_resume(tmp_path):
    client = FixtureClient()
    a = fetch_homologs([Seed('1', 'a')], target_organisms=['2', '1', '2'], output_dir=tmp_path, client=client)
    count = len(client.calls)
    b = fetch_homologs([Seed('1', 'a')], target_organisms=['1', '2'], output_dir=tmp_path, client=client)
    assert a.manifest == b.manifest
    assert len(client.calls) == count


def test_old_processed_result_rebuilds_from_raw_cache(tmp_path):
    from phytominer.storage import atomic_json, digest
    from dataclasses import asdict
    client = FixtureClient()
    seed = Seed('1', 'a')
    original = fetch_homologs([seed], output_dir=tmp_path, client=client)
    old = dict(original.manifest)
    old['identity'] = digest({'seeds':[asdict(seed)], 'targets':[], 'depth':0,
        'metadata':client.metadata_fingerprint, 'endpoint':client.config.endpoint,
        'dataset':client.config.dataset, 'virtual_schema':client.config.virtual_schema})
    atomic_json(tmp_path/'manifest.json', old)
    count = len(client.calls)
    rebuilt = fetch_homologs([seed], output_dir=tmp_path, client=client)
    assert rebuilt.manifest['identity'] != old['identity']
    assert rebuilt.manifest['tables']['relationships']['file'] != original.manifest['tables']['relationships']['file']
    assert len(client.calls) == count

@pytest.mark.parametrize('targets,depth,expected', [(None, 0, 1), ([], 0, 0), (['1','2'], 3, 2)])
def test_selection_refresh_and_resume(tmp_path, targets, depth, expected):
    client = FixtureClient()
    kwargs = dict(target_organisms=targets, expansion_depth=depth, output_dir=tmp_path, client=client)
    first = fetch_homologs([Seed('1','a')], **kwargs)
    count = len(client.calls)
    resumed = fetch_homologs([Seed('1','a')], **kwargs)
    assert first.manifest == resumed.manifest
    assert len(client.calls) == count
    refreshed = fetch_homologs([Seed('1','a')], refresh=True, **kwargs)
    assert len(client.calls) > count
    assert refreshed.scan('relationships').collect().height == expected
    count = len(client.calls)
    fetch_homologs([Seed('1','a')], **kwargs)
    assert len(client.calls) == count


def test_expansion_empty_boundary_rejected(tmp_path):
    with pytest.raises(ValidationError, match='boundary'):
        fetch_homologs([Seed('1','a')], target_organisms=[], expansion_depth=1, output_dir=tmp_path)
    assert not tmp_path.joinpath('manifest.json').exists()

class MissingFeatures(FixtureClient):
    def __init__(self, missing, config=None):
        super().__init__(config)
        self.missing = missing

    def query(self, page, genes=(), organism_id=None):
        for batch in super().query(page, genes, organism_id):
            if page != 'orthologs':
                batch = [row for row in batch if row['organism_name'] not in self.missing]
            yield batch


def test_missing_source_preserves_request_identity(tmp_path):
    result = fetch_homologs([Seed('1','a')], output_dir=tmp_path, client=MissingFeatures({'org1'}))
    edge = result.scan('relationships').collect().to_dicts()[0]
    assert edge['source_organism_id'] == '1'
    assert edge['source_organism_name'] == 'org1'
    assert result.scan('provenance').collect().height == 1


def test_shared_gene_name_keeps_source_context(tmp_path):
    result = fetch_homologs([Seed('1','a'), Seed('2','a')], output_dir=tmp_path, client=FixtureClient())
    assert result.scan('relationships').collect()['source_organism_id'].to_list() == ['1', '2']


def test_unexpected_source_is_rejected(tmp_path):
    class Unexpected(FixtureClient):
        def query(self, page, genes=(), organism_id=None):
            for batch in super().query(page, genes, organism_id):
                if page == 'orthologs':
                    for row in batch: row['ortholog__dm_gene_name'] = 'unexpected'
                yield batch
    with pytest.raises(Exception, match='unexpected source'):
        fetch_homologs([Seed('1','a')], output_dir=tmp_path, client=Unexpected())


def test_conflicting_source_feature_identity_rejected(tmp_path):
    class Conflict(FixtureClient):
        def query(self, page, genes=(), organism_id=None):
            for batch in super().query(page, genes, organism_id):
                if page != 'orthologs':
                    for row in batch:
                        if row['organism_name'] == 'org1': row['organism_id'] = '99'
                yield batch
    with pytest.raises(Exception, match='conflicts'):
        fetch_homologs([Seed('1','a')], output_dir=tmp_path, client=Conflict())

@pytest.mark.parametrize('missing,source_status,target_status', [
    (set(), 'resolved', 'resolved'),
    ({'org1'}, 'missing_feature', 'resolved'),
    ({'org2'}, 'resolved', 'missing_feature'),
    ({'org1','org2'}, 'missing_feature', 'missing_feature'),
])
def test_resolution_status_preserves_both_sides(tmp_path, missing, source_status, target_status):
    result = fetch_homologs([Seed('1','a')], target_organisms=['org2'], expansion_depth=2,
        output_dir=tmp_path, client=MissingFeatures(missing))
    rows = result.scan('relationships').collect().to_dicts()
    edge = next(row for row in rows if row['source_gene_name'] == 'a')
    assert edge['source_organism_id'] == '1'
    assert edge['source_resolution_status'] == source_status
    assert edge['target_resolution_status'] == target_status
    if 'org2' in missing:
        assert edge['target_organism_id'] is None
    expected = sum(row['source_resolution_status'] == 'missing_feature' or row['target_resolution_status'] == 'missing_feature' for row in rows)
    assert result.manifest['unresolved_identity_rows'] == expected
    assert result.scan('unresolved_relationships').collect().height == expected
    assert result.scan('provenance').collect().height >= 1


def test_schema_one_still_opens_without_fabricated_statuses(tmp_path):
    from phytominer.models import TABLES_V1
    from phytominer.storage import write_batches, atomic_json
    from phytominer.dataset import HomologDataset
    columns = TABLES_V1['relationships']
    values = ['1','org1','a','2','org2','b','group','one-to-one']
    record = write_batches(tmp_path/'old.parquet', columns, [[dict(zip(columns, values))]])
    atomic_json(tmp_path/'manifest.json', {'schema_version':1, 'status':'complete', 'identity':'old',
        'tables':{'relationships':{'file':'old.parquet', 'rows':record['rows'], 'sha256':record['sha256']}}})
    dataset = HomologDataset(tmp_path)
    assert dataset.scan('relationships').collect_schema().names() == list(columns)
    assert dataset.summary().collect()['reported_edges'].to_list() == [1]
    with dataset.connect() as connection:
        assert connection.sql('select count(*) from relationships').fetchall() == [(1,)]


@pytest.mark.parametrize('workers', [1,2,4])
def test_schema_two_deterministic_missing_evidence(tmp_path, workers):
    from phytominer import ClientConfig
    result = fetch_homologs([Seed('1','a','X'),Seed('1','a','Y'),Seed('2','b')],
        target_organisms=['org1','org2'], expansion_depth=3, output_dir=tmp_path,
        client=MissingFeatures({'org1'}, ClientConfig(max_workers=workers)))
    assert result.manifest['schema_version'] == 3
    assert result.scan('relationships').collect().height == 2
    assert result.scan('provenance').collect().height == 3
    assert result.manifest['unresolved_identity_rows'] == 2
    assert result.scan('seeds').collect().height == 3


def test_combined_selection_missing_source_and_failed_refresh(tmp_path, monkeypatch):
    from phytominer.dataset import DatasetWriter, HomologDataset
    original_client = FixtureClient()
    original = fetch_homologs([Seed('1','a')], output_dir=tmp_path, client=original_client)
    assert original.scan('relationships').collect()['source_resolution_status'].to_list() == ['resolved']
    empty = fetch_homologs([Seed('1','a')], target_organisms=[], output_dir=tmp_path, client=original_client)
    assert empty.scan('relationships').collect().is_empty()
    before = (tmp_path/'manifest.json').read_bytes()
    missing = MissingFeatures({'org1'})
    write = DatasetWriter.write
    def fail_relationships(self, name, frame):
        if name == 'relationships': raise OSError('interrupted replacement')
        return write(self, name, frame)
    with monkeypatch.context() as patch:
        patch.setattr(DatasetWriter, 'write', fail_relationships)
        with pytest.raises(OSError, match='interrupted'):
            fetch_homologs([Seed('1','a')], target_organisms=['org2'], output_dir=tmp_path, client=missing, refresh=True)
    assert (tmp_path/'manifest.json').read_bytes() == before
    assert HomologDataset(tmp_path).scan('relationships').collect().is_empty()
    count = len(missing.calls)
    rebuilt = fetch_homologs([Seed('1','a')], target_organisms=['org2'], output_dir=tmp_path, client=missing)
    assert len(missing.calls) == count
    assert rebuilt.manifest['unresolved_identity_rows'] == 1
    assert rebuilt.scan('relationships').collect()['source_organism_id'].to_list() == ['1']
    assert original.scan('relationships').collect()['source_resolution_status'].to_list() == ['resolved']
    assert empty.scan('relationships').collect().is_empty()


def test_candidate_validation_failure_during_refresh_keeps_old(tmp_path, monkeypatch):
    import phytominer.dataset as module
    original = fetch_homologs([Seed('1','a')], output_dir=tmp_path, client=FixtureClient())
    before = (tmp_path/'manifest.json').read_bytes()
    validate = module._validate_manifest
    def reject_candidate(root, manifest):
        if manifest['created_at'] != original.manifest['created_at']:
            raise IncompleteDatasetError('injected candidate rejection')
        return validate(root, manifest)
    from phytominer import IncompleteDatasetError
    with monkeypatch.context() as patch:
        patch.setattr(module, '_validate_manifest', reject_candidate)
        with pytest.raises(IncompleteDatasetError, match='candidate rejection'):
            fetch_homologs([Seed('1','a')], output_dir=tmp_path, client=FixtureClient(), refresh=True)
    assert (tmp_path/'manifest.json').read_bytes() == before
    assert module.HomologDataset(tmp_path).manifest == original.manifest


def test_normalization_ignores_raw_column_order_and_context_position(tmp_path, monkeypatch):
    import phytominer.workflows as module
    raw = module._raw
    def reorder(*args, **kwargs):
        frame = raw(*args, **kwargs)
        if frame is not None:
            names = frame.collect_schema().names()
            if '_requested_source_organism_id' in names:
                return frame.select(list(reversed(names)))
        return frame
    monkeypatch.setattr(module, '_raw', reorder)
    dataset = fetch_homologs([Seed('1','a')], output_dir=tmp_path, client=FixtureClient())
    edge = dataset.scan('relationships').collect().to_dicts()[0]
    assert (edge['source_organism_id'], edge['source_gene_name'], edge['target_gene_name']) == ('1','a','b')
