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
