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
