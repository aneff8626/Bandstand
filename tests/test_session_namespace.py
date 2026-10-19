import unittest
from unittest.mock import patch
import session_vault

class NamespaceTests(unittest.TestCase):
 def test_production_compatible_and_staging_separate(self):
  with patch.object(session_vault.backend_config,'load',return_value={'name':'production'}):
   production=session_vault.session_namespace()
   self.assertEqual(production,str(session_vault.DATA_ROOT))
  with patch.object(session_vault.backend_config,'load',return_value={'name':'staging','url':'https://aaaaaaaaaaaaaaaaaaaa.supabase.co'}):
   self.assertNotEqual(production,session_vault.session_namespace())
