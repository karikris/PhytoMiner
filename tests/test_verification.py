import json
import pytest
from phytominer import HomologDataset, IncompleteDatasetError, ValidationError
from test_derived import parent

def test_verification_modes(tmp_path):
    parent(tmp_path,'a')
    path=tmp_path/'manifest.json';m=json.loads(path.read_text())
    m['tables']['genes']['sha256']='bad';path.write_text(json.dumps(m))
    with pytest.raises(IncompleteDatasetError):HomologDataset(tmp_path)
    fast=HomologDataset(tmp_path,verify='metadata')
    assert fast.verification_mode=='metadata'
    assert fast.scan('genes').collect().height==1
    m['tables']['genes']['rows']=99;path.write_text(json.dumps(m))
    with pytest.raises(IncompleteDatasetError):HomologDataset(tmp_path,verify='metadata')
    with pytest.raises(ValidationError):HomologDataset(tmp_path,verify='none')
