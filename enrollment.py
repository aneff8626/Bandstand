"""Local consent only. No research upload transport exists in this module."""
import json, os, time
from private_storage import DATA_ROOT
POLICY_VERSION = '2026-10-08-draft'

def enrollment(body=None):
    path = DATA_ROOT/'enrollment.json'
    if body is not None:
        if body.get('policy_version') != POLICY_VERSION or body.get('acknowledged') is not True:
            raise ValueError('Read and acknowledge the current privacy notice')
        record = {'policy_version':POLICY_VERSION,'acknowledged':True,
                  'erp_sharing_requested':body.get('erp_sharing_requested') is True,
                  'decoder_sharing_requested':False,'updated_at':time.time()}
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(record,indent=2));temp.chmod(0o600);os.replace(temp,path)
    record = json.loads(path.read_text()) if path.exists() else {}
    return {'consent':record,'policy_version':POLICY_VERSION,'erp_upload_enabled':False,
            'decoder_upload_enabled':False,'accounts_enabled':True}
