import pytest
from phytominer.biomart import BioMartClient
from phytominer.models import ORTHOLOG_ATTRIBUTES, FEATURE_ATTRIBUTES, ServiceError, ValidationError

@pytest.fixture
def metadata():
    return {'registry': '<MartRegistry><MartURLLocation serverVirtualSchema="zome_mart"/></MartRegistry>',
        'datasets': 'TableSet\tphytozome\tGenomes',
        'attributes': '\n'.join(f'{name}\tlabel\t\t{page}' for page, names in [('orthologs', ORTHOLOG_ATTRIBUTES), ('features', FEATURE_ATTRIBUTES)] for name in names),
        'filters': 'organism_id\tID\ngene_name_filter\tName'}

def test_metadata(metadata):
    client = BioMartClient()
    client.validate_metadata(metadata)
    client._metadata = metadata
    assert len(client.metadata_fingerprint) == 64
    metadata['attributes'] = ''
    with pytest.raises(ServiceError, match='attributes'):
        client.validate_metadata(metadata)

def test_organism_resolution():
    cat = [{'organism_id': '167', 'organism_name': 'TAIR10'}, {'organism_id': '2', 'organism_name': 'other'}]
    assert BioMartClient.resolve_organism('TAIR10', cat) == '167'
    with pytest.raises(ValidationError):
        BioMartClient.resolve_organism('unknown', cat)
    cat.append({'organism_id': '3', 'organism_name': 'TAIR10'})
    with pytest.raises(ValidationError):
        BioMartClient.resolve_organism('TAIR10', cat)

def test_xml_escaping():
    import xml.etree.ElementTree as ET
    xml, columns = BioMartClient().build_query('orthologs', ['a&<b'], '167')
    root = ET.fromstring(xml)
    assert root.find('.//Filter[@name="gene_name_filter"]').get('value') == 'a&<b'
    assert tuple(x.get('name') for x in root.findall('.//Attribute')) == columns
    with pytest.raises(ValidationError):
        BioMartClient().build_query('unsupported', ['x'], '1')

@pytest.mark.parametrize('lines', [['x'], ['Query ERROR: bad'], ['<html>login'], ['[success]', 'x\ty']])
def test_bad_responses(lines):
    with pytest.raises(ServiceError):
        list(BioMartClient.parse_lines(lines, ('a','b')))

def test_empty_and_bounded_responses():
    assert list(BioMartClient.parse_lines(['[success]'], ('a','b'))) == []
    assert list(BioMartClient.parse_lines(['x\t', 'y\tz', '[success]'], ('a','b'), batch_size=1)) == [[{'a':'x','b':None}], [{'a':'y','b':'z'}]]

def test_metadata_snapshot_supports_offline_resume(tmp_path,metadata):
    from phytominer.storage import RequestCache
    first=BioMartClient(); first._metadata=metadata
    cache=RequestCache(tmp_path)
    fingerprint=cache.metadata(first)
    second=BioMartClient()
    def offline(*args,**kwargs): raise AssertionError('unexpected network')
    second._request=offline
    assert cache.metadata(second)==fingerprint
