import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import erp_sharing
class ERPSharingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.folder=self.root/'abc123';self.folder.mkdir()
  self.session={'mode':'erp','source':'live','protocol':'oddball','running':False,'title':'PRIVATE_TEXT'}
  self.trial={'condition_index':0,'times':[-.2,0,.2],'onset':123456,'note':'PRIVATE_TEXT','channel_trials':{'TP9':{'accepted':True,'wave':[1,2,3],'reasons':['PRIVATE_TEXT']}}}
  self.write()
  p=patch.object(erp_sharing,'DATA_ROOT',self.root);p.start();self.addCleanup(p.stop)
 def write(self):
  (self.folder/'session.json').write_text(json.dumps(self.session));(self.folder/'trials.json').write_text(json.dumps([self.trial]))
 def test_only_numeric_trials_and_known_protocol_leave(self):
  ident,result=erp_sharing.payload('abc123');encoded=json.dumps(result)
  self.assertNotIn('PRIVATE_TEXT',encoded);self.assertNotIn('onset',encoded)
  self.assertEqual(result['trials'][0]['channels']['TP9']['wave'],[1,2,3])
  self.assertEqual(ident,erp_sharing.payload('abc123')[0])
 def test_forbids_writing_custom_simulation_and_active_sessions(self):
  for field,value in [('mode','typing'),('protocol','custom'),('source','simulation'),('running',True)]:
   original=self.session[field];self.session[field]=value;self.write()
   with self.assertRaises(ValueError):erp_sharing.payload('abc123')
   self.session[field]=original
 def test_rejects_text_in_waveforms(self):
  self.trial['channel_trials']['TP9']['wave']=['PRIVATE_TEXT'];self.write()
  with self.assertRaises(ValueError):erp_sharing.payload('abc123')
 def test_path_traversal_rejected(self):
  with self.assertRaises(ValueError):erp_sharing.payload('../typing')
