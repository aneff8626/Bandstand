"""Local consent only. No research upload transport exists in this module."""
import json, os, time
from private_storage import DATA_ROOT
from sharing_policy import POLICY_VERSION, choices

def enrollment(body=None):
    path = DATA_ROOT/'enrollment.json'
    if body is not None:
        if body.get('policy_version') != POLICY_VERSION or body.get('acknowledged') is not True:
            raise ValueError('Read and acknowledge the current privacy notice')
        record = {**choices(body), 'decoder_sharing_requested':False, 'updated_at':time.time()}
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(record,indent=2));temp.chmod(0o600);os.replace(temp,path)
    record = json.loads(path.read_text()) if path.exists() else {}
    from accounts import ERP_SHARING_AVAILABLE
    return {'consent':record,'policy_version':POLICY_VERSION,'erp_upload_enabled':ERP_SHARING_AVAILABLE,
            'decoder_upload_enabled':False,'accounts_enabled':True}
