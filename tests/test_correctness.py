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
