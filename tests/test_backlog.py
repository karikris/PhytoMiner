import json
from pathlib import Path


def test_backlog_payload_inventory():
    payload = json.loads(Path('docs/backlog-issues.json').read_text())
    assert payload['repository'] == 'karikris/PhytoMiner'
    issues = payload['issues']
    ids = {issue['id'] for issue in issues}
    assert len(issues) == 26 and ids == {f'B{i:02}' for i in range(1,27)}
    assert {i['id'] for i in issues if i['close_after_verified']} == {'B02','B09','B11'}
    for issue in issues:
        assert set(issue['dependencies']) <= ids - {issue['id']}
        assert len(issue['acceptance']) >= 3
        assert f'<!-- phytominer-backlog:{issue["id"]} -->' in issue['body']
        assert '### Problem' in issue['body'] and '### Scope' in issue['body']
        assert '{{release_sha}}' in issue['body'] and '{{ci_url}}' in issue['body']
        assert set(issue['labels']) <= {'bug','enhancement','documentation'}
