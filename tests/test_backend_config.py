import json,tempfile,unittest
from pathlib import Path
import backend_config
STAGING={'name':'staging','url':'https://abcdefghijklmnopqrst.supabase.co','publishable_key':'sb_publishable_synthetic-Key_0123'}
class BackendConfigTests(unittest.TestCase):
 def load(self,config,raw=None):
  with tempfile.TemporaryDirectory() as root:
   Path(root,'backend.json').write_text(raw if raw is not None else json.dumps(config))
   return backend_config.load(root)
 def test_production_is_default_without_file(self):
  with tempfile.TemporaryDirectory() as root:self.assertEqual(backend_config.load(root),backend_config.PRODUCTION)
 def test_valid_staging_and_local_development(self):
  self.assertEqual(self.load(STAGING),STAGING)
  local={'name':'development','url':'http://127.0.0.1:54321','publishable_key':'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH'}
  self.assertEqual(self.load(local),local)
  self.assertEqual(self.load({**STAGING,'url':STAGING['url']+'/'})['url'],STAGING['url'])
 def test_rejects_unsafe_destinations_and_keys(self):
  bad=[{**STAGING,'name':'production'},{**STAGING,'url':backend_config.PRODUCTION['url']},
   {**STAGING,'url':'http://abcdefghijklmnopqrst.supabase.co'},{**STAGING,'url':'https://evil.example'},
   {**STAGING,'url':'https://abcdefghijklmnopqrst.supabase.co.evil.example'},{**STAGING,'url':'https://abcdefghijklmnopqrst.supabase.co/rest/v1'},
   {**STAGING,'url':'https://abcdefghijklmnopqrst.supabase.co?x=1'},{**STAGING,'url':'https://user@abcdefghijklmnopqrst.supabase.co'},
   {**STAGING,'url':'https://abcdefghijklmnopqrst.supabase.co:8443'},{**STAGING,'url':'http://127.0.0.1:54321'},
   {**STAGING,'name':'development','url':'http://192.168.1.5:54321'},{**STAGING,'name':'development','url':'http://127.0.0.1'},
   {**STAGING,'publishable_key':'sb_'+'secret_synthetic0123456789'},{**STAGING,'publishable_key':'eyJhbGciOiJIUzI1NiJ9.service_role'},
   {**STAGING,'service_role_key':'x'},{'url':STAGING['url']},[STAGING],{**STAGING,'url':5}]
  for config in bad:
   with self.subTest(config=config),self.assertRaises(ValueError):self.load(config)
 def test_unreadable_or_linked_file_fails_closed(self):
  with self.assertRaises(ValueError):self.load(None,raw='{not json')
  with tempfile.TemporaryDirectory() as root:
   target=Path(root,'real.json');target.write_text(json.dumps(STAGING));Path(root,'backend.json').symlink_to(target)
   with self.assertRaises(ValueError):backend_config.load(root)
 def test_accounts_use_configured_backend_and_report_it(self):
  import accounts
  self.assertEqual((accounts.URL,accounts.PUBLISHABLE_KEY),(accounts.BACKEND['url'],accounts.BACKEND['publishable_key']))
  self.assertEqual(accounts._status()['backend'],accounts.BACKEND['name'])
