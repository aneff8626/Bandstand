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
 def test_client_still_sends_v1_until_notice_updated(self):
  self.assertEqual(erp_sharing.SCHEMA,'bandstand-erp-v1')
  _,result=erp_sharing.payload('abc123');self.assertEqual(set(result),{'schema','protocol','trials'})
  self.assertEqual(set(result['trials'][0]['channels']['TP9']),{'accepted','wave'})
 def test_v2_adds_only_allowlisted_metadata_and_categories(self):
  self.session.update(channels=['TP9','TP10'],window=[.3,.5],trials_planned=120,end_reason='PRIVATE_TEXT stopped');self.write()
  self.trial['channel_trials']['AF7']={'accepted':False,'wave':None,'reasons':['probable blink','signal clipping','PRIVATE_TEXT']};self.write()
  _,result=erp_sharing.payload('abc123','bandstand-erp-v2');encoded=json.dumps(result)
  self.assertNotIn('PRIVATE_TEXT',encoded);self.assertNotIn('onset',encoded)
  self.assertEqual(set(result),{'schema','protocol','trials','recording'})
  self.assertEqual(set(result['recording']),{'app_version','sample_rate_hz','units','reference','channels','preprocessing','grid','epoch_s','baseline_s','analysis_window_s','trials_planned','trials_presented','end'})
  r=result['recording'];self.assertEqual((r['trials_planned'],r['trials_presented'],r['end'],r['channels'],r['reference']),(120,1,'interrupted',['TP9','TP10'],'FPz'))
  self.assertEqual(result['trials'][0]['channels']['AF7']['rejection'],['blink','clipping','other'])
  self.assertEqual(result['trials'][0]['channels']['TP9']['rejection'],['other'])
 def test_v2_end_categories(self):
  for reason,want in (('completed','completed'),('stopped by participant','stopped'),('signal lost','interrupted'),(None,'interrupted')):
   self.session.update(window=[.3,.5],end_reason=reason);self.write()
   self.assertEqual(erp_sharing.payload('abc123','bandstand-erp-v2')[1]['recording']['end'],want)
 def test_unknown_schema_refused(self):
  with self.assertRaises(ValueError):erp_sharing.payload('abc123','bandstand-erp-v9')
