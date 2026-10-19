import json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from session_store import saved_sessions,delete_session

class Sessions(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.engine=SimpleNamespace(lock=threading.RLock(),session=None,personal=SimpleNamespace(current=None),typing=SimpleNamespace(running=False,fitting=False))
 def tearDown(self):self.temp.cleanup()
 def session(self,ident):
  p=self.root/ident;p.mkdir();(p/'session.json').write_text(json.dumps({'id':ident,'mode':'erp'}));return p
 def delete(self,ident,kind='lab'):return delete_session(self.engine,{'id':ident,'kind':kind,'confirmation':ident},self.root)
 def test_channel_acceptance_counts(self):
  p=self.session('one');(p/'trials.json').write_text(json.dumps([{'accepted':False,'channel_trials':{'TP9':{'accepted':False},'TP10':{'accepted':True}}}]))
  self.assertEqual(saved_sessions(self.root)[0]['quality_metrics'],{'usable':1,'total':1})
 def test_delete_only_selected_session(self):
  one=self.session('one');two=self.session('two');self.delete('one');self.assertFalse(one.exists());self.assertTrue(two.exists())
 def test_confirmation_required(self):
  self.session('one')
  with self.assertRaises(ValueError):delete_session(self.engine,{'id':'one','kind':'lab'},self.root)
  self.assertTrue((self.root/'one').exists())
 def test_active_refused(self):
  self.session('one');self.engine.session={'id':'one','running':True}
  with self.assertRaises(ValueError):self.delete('one')
 def test_traversal_refused(self):
  with self.assertRaises(ValueError):self.delete('../one')
 def test_link_refused(self):
  p=self.session('two');(self.root/'one').symlink_to(p,target_is_directory=True)
  with self.assertRaises(ValueError):self.delete('one')
  self.assertTrue(p.exists())
 def test_personal_deletes_raw_and_cache(self):
  p=self.root/'personal';p.mkdir();(p/'record-one.json').write_text(json.dumps({'id':'one','raw_eeg_file':'raw-one.jsonl'}));(p/'raw-one.jsonl').write_text('');(p/'spectral-one.json').write_text('{}');(p/'record-two.json').write_text('{"id":"two"}')
  self.delete('one','personal');self.assertEqual([x.name for x in p.iterdir()],['record-two.json'])
if __name__=='__main__':unittest.main()
