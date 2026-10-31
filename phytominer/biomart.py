"""BioMart metadata and XML adapter. External field names stay in this module."""
import hashlib
import json
import xml.etree.ElementTree as ET
lazy import requests
from .models import ClientConfig, ServiceError, ValidationError, ORTHOLOG_ATTRIBUTES, FEATURE_ATTRIBUTES

class BioMartClient:
    def __init__(self, config=None):
        self.config = config or ClientConfig()
        self._metadata = None
        self._sessions = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        for session in self._sessions:
            session.close()
        self._sessions.clear()

    def _request(self, method, **kwargs):
        session = requests.Session()
        self._sessions.append(session)
        try:
            response = session.request(method, self.config.endpoint,
                timeout=(self.config.connect_timeout, self.config.read_timeout), **kwargs)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response
        except requests.RequestException as exc:
            raise ServiceError('BioMart request failed') from exc

    def metadata(self):
        if self._metadata is not None:
            return self._metadata
        result = {}
        for kind, params in [('registry', {}), ('datasets', {'mart': 'phytozome_mart'}),
                             ('attributes', {'dataset': self.config.dataset}), ('filters', {'dataset': self.config.dataset})]:
            with self._request('GET', params={'type': kind, **params}) as response:
                result[kind] = response.text
        self.validate_metadata(result)
        self._metadata = result
        return result

    def validate_metadata(self, metadata):
        try:
            registry = ET.fromstring(metadata['registry'])
            if not any(x.get('serverVirtualSchema') == self.config.virtual_schema for x in registry):
                raise ValueError('virtual schema missing')
            datasets = [x.split('\t')[1] for x in metadata['datasets'].splitlines() if x.startswith('TableSet\t')]
            if self.config.dataset not in datasets:
                raise ValueError('dataset missing')
            attrs = {(r[0], r[3]) for line in metadata['attributes'].splitlines() if len(r := line.split('\t')) >= 4}
            for page, names in [('orthologs', ORTHOLOG_ATTRIBUTES), ('features', FEATURE_ATTRIBUTES)]:
                if any((name, page) not in attrs for name in names):
                    raise ValueError(f'required {page} attributes missing')
            filters = {line.split('\t')[0] for line in metadata['filters'].splitlines()}
            if not {'organism_id', 'gene_name_filter'} <= filters:
                raise ValueError('required filters missing')
        except (KeyError, ET.ParseError, ValueError) as exc:
            raise ServiceError(f'Unsupported BioMart metadata: {exc}') from exc

    @property
    def metadata_fingerprint(self):
        return hashlib.sha256(json.dumps(self.metadata(), sort_keys=True).encode()).hexdigest()

    @staticmethod
    def resolve_organism(value, catalog):
        matches = {row['organism_id'] for row in catalog if value in (row['organism_id'], row['organism_name'])}
        if len(matches) != 1:
            raise ValidationError(f'Unknown or ambiguous organism: {value}')
        return matches.pop()

    def build_query(self, page, genes=(), organism_id=None):
        attrs = {'orthologs': ORTHOLOG_ATTRIBUTES, 'features': FEATURE_ATTRIBUTES,
                 'organisms': ('organism_id', 'organism_name')}
        if page not in attrs:
            raise ValidationError(f'Unsupported query page: {page}')
        if page != 'organisms' and (not genes or not organism_id):
            raise ValidationError('Gene queries require identifiers and a source organism')
        from .models import Seed
        for gene in genes:
            Seed(str(organism_id), gene)
        root = ET.Element('Query', virtualSchemaName=self.config.virtual_schema,
            formatter='TSV', header='0', uniqueRows='1', count='',
            datasetConfigVersion='0.6', completionStamp='1')
        dataset = ET.SubElement(root, 'Dataset', name=self.config.dataset, interface='default')
        if organism_id is not None:
            ET.SubElement(dataset, 'Filter', name='organism_id', value=str(organism_id))
        if genes:
            ET.SubElement(dataset, 'Filter', name='gene_name_filter', value=','.join(sorted(set(genes))))
        for name in attrs[page]:
            ET.SubElement(dataset, 'Attribute', name=name)
        return ET.tostring(root, encoding='unicode'), attrs[page]

    @staticmethod
    def parse_lines(lines, columns, batch_size=4096):
        batch, complete = [], False
        for line in lines:
            if not line:
                continue
            if complete:
                raise ServiceError('Data after BioMart completion marker')
            if line == '[success]':
                complete = True
                continue
            if line.startswith('<') or 'Query ERROR' in line or 'Exception' in line:
                raise ServiceError('BioMart returned an error or HTML response')
            fields = line.split('\t')
            if len(fields) != len(columns):
                raise ServiceError('Malformed BioMart TSV row')
            batch.append(dict(zip(columns, (value or None for value in fields))))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if not complete:
            raise ServiceError('Missing BioMart completion marker; response may be truncated')
        if batch:
            yield batch

    def query(self, page, genes=(), organism_id=None):
        self.metadata()
        xml, columns = self.build_query(page, genes, organism_id)
        try:
            with self._request('POST', data={'query': xml}, stream=True) as response:
                yield from self.parse_lines(response.iter_lines(decode_unicode=True), columns)
        except requests.RequestException as exc:
            raise ServiceError('BioMart response stream failed') from exc

    def organisms(self):
        return sorted((row for batch in self.query('organisms') for row in batch), key=lambda row: row['organism_id'])
