import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('launcher',Path(__file__).parents[1]/'scripts/launch_development.py');launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
class DevelopmentLauncherTests(unittest.TestCase):
 def test_refuses_missing_and_production(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'web').mkdir();(root/'web/index.html').write_text('test');(root/'desktop_service.py').write_text('')
   with self.assertRaises(ValueError):launcher.validate_checkout(root)
   for config in [dict(name='production',url=launcher.backend_config.PRODUCTION['url'],publishable_key='sb_publishable_test_fixture'),dict(name='staging',url=launcher.backend_config.PRODUCTION['url'],publishable_key='sb_publishable_test_fixture'),dict(name='staging',url=launcher.backend_config.PRODUCTION['url'].upper(),publishable_key='sb_publishable_test_fixture'),dict(name='development',url='http://127.0.0.1:54321',publishable_key='service-role-not-allowed')]:
    (root/'backend.json').write_text(json.dumps(config))
    with self.assertRaises(ValueError):launcher.validate_checkout(root)
 def test_accepts_local_development(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'web').mkdir();(root/'web/index.html').write_text('test');(root/'desktop_service.py').write_text('')
   (root/'backend.json').write_text(json.dumps(dict(name='development',url='http://localhost:54321',publishable_key='sb_publishable_test_fixture')))
   self.assertEqual(launcher.validate_checkout(root)['name'],'development')
 def test_normal_backend_and_session_namespace_preserved(self):
  import backend_config,session_vault
  with tempfile.TemporaryDirectory() as folder:self.assertEqual(backend_config.load(Path(folder)),backend_config.PRODUCTION)
  with patch.object(session_vault.backend_config,'load',return_value=backend_config.PRODUCTION):self.assertEqual(session_vault.session_namespace(),str(session_vault.DATA_ROOT))
  with patch.object(session_vault.backend_config,'load',return_value={'name':'development','url':'http://localhost:54321'}):self.assertIn('|http://localhost:54321',session_vault.session_namespace())
if __name__=='__main__':unittest.main()
