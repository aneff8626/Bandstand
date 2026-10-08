import json,tempfile,unittest,socket
from pathlib import Path
from unittest.mock import patch
import enrollment
class PrivacyTests(unittest.TestCase):
 def test_consent_cannot_enable_uploads_or_store_payloads(self):
  with tempfile.TemporaryDirectory() as d,patch.object(enrollment,'DATA_ROOT',Path(d)),patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')),patch('accounts.ERP_SHARING_AVAILABLE',False):
   result=enrollment.enrollment({'policy_version':enrollment.POLICY_VERSION,'acknowledged':True,'erp_sharing_requested':True,'decoder_sharing_requested':True,'text':'PRIVATE_CANARY_92','embedding':[1,2],'eeg':[3,4]})
   self.assertFalse(result['decoder_upload_enabled']);self.assertFalse(result['erp_upload_enabled'])
   record=(Path(d)/'enrollment.json').read_text();self.assertNotIn('PRIVATE_CANARY',record);self.assertNotIn('embedding',record);self.assertNotIn('eeg',record)
   self.assertFalse(result['consent']['decoder_sharing_requested'])
 def test_acknowledgment_required(self):
  with self.assertRaises(ValueError):enrollment.enrollment({'acknowledged':False})
