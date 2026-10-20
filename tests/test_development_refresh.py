import tempfile, threading, unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from development import DevelopmentRefresh

class RefreshTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);(self.root/'web').mkdir();(self.root/'web/style.css').write_text('body{}')
  self.engine=NS(lock=threading.RLock(),session=None,typing=NS(running=False,fitting=False),personal=NS(current=None),developer=NS(current=None))
  with patch('backend_config.load',return_value={'name':'development'}):
   self.refresh=DevelopmentRefresh(self.root,Path.home()/'Library/Application Support/Bandstand Development/data')
 def change(self,name,text):
  (self.root/name).write_text(text);s=self.refresh.status(self.engine);self.refresh.changed_at-=3;return s['revision']
 def test_css_only_and_revision_race(self):
  rev=self.change('web/style.css','body{color:red}')
  self.assertFalse(self.refresh.apply(self.engine,rev-1)['ready'])
  self.assertEqual(self.refresh.apply(self.engine,rev),{'ready':True,'restart':False})
  self.assertFalse(self.refresh.status(self.engine)['changed'])
 def test_recording_and_fitting_defer(self):
  rev=self.change('worker.py','a=1')
  for obj,attr,value in [(self.engine,'session',{'running':True}),(self.engine.typing,'running',True),(self.engine.typing,'fitting',True),(self.engine.personal,'current',{'task':'survey'}),(self.engine.developer,'current',{'task':'artifact'})]:
   old=getattr(obj,attr);setattr(obj,attr,value)
   self.assertFalse(self.refresh.apply(self.engine,rev)['ready']);setattr(obj,attr,old)
  self.assertEqual(self.refresh.apply(self.engine,rev),{'ready':True,'restart':True})
 def test_bad_python_does_not_restart(self):
  rev=self.change('worker.py','def !')
  with self.assertRaises(SyntaxError):self.refresh.apply(self.engine,rev)
  self.assertFalse(self.refresh.restart)
 def test_backend_or_dependency_change_requires_manual(self):
  for name in ('backend.json','requirements.txt'):
   rev=self.change(name,'changed');self.assertTrue(self.refresh.status(self.engine)['manual']);self.assertFalse(self.refresh.apply(self.engine,rev)['ready'])
 def test_normal_app_never_refreshes(self):
  with patch('backend_config.load',return_value={'name':'production'}):r=DevelopmentRefresh(self.root,self.root/'data')
  self.assertEqual(r.status(self.engine),{'enabled':False})
  with patch('backend_config.load',return_value={'name':'development'}):r=DevelopmentRefresh(self.root,self.root/'data')
  self.assertFalse(r.enabled)
