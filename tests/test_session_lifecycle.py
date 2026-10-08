import unittest,time
from unittest.mock import patch
import accounts
class SessionLifecycleTests(unittest.TestCase):
 def setUp(self):
  accounts._session=None;accounts._restore_attempted=False;accounts._restore_retry_at=0;accounts._session_notice=''
 def tearDown(self):self.setUp()
 def test_remembered_refresh_rotates_secret_without_returning_it(self):
  with patch('session_vault.load',return_value='synthetic-refresh'),patch('session_vault.save') as save,patch.object(accounts,'_request',side_effect=[{'access_token':'synthetic-access','refresh_token':'rotated','expires_in':3600},{'id':'u','email':'test@example.org'}]):
   state=accounts.account('status');self.assertTrue(state['signed_in']);self.assertTrue(state['remembered']);self.assertNotIn('rotated',str(state));save.assert_called_once_with('rotated')
 def test_expired_invalid_session_cleared(self):
  accounts._session={'token':'expired','refresh_token':'bad','expires_at':0}
  with patch('session_vault.clear') as clear,patch.object(accounts,'_request',side_effect=accounts.AccountError('expired',401)):
   state=accounts.account('status');self.assertFalse(state['signed_in']);clear.assert_called_once()
 def test_transient_failure_can_retry(self):
  with patch('session_vault.load',return_value='synthetic'),patch.object(accounts,'_request',side_effect=ValueError('offline')):
   self.assertFalse(accounts.account('status')['signed_in']);self.assertFalse(accounts._restore_attempted);self.assertGreater(accounts._restore_retry_at,time.time())
 def test_unremembered_session_refresh_stays_memory_only(self):
  accounts._session={'token':'old','refresh_token':'r','expires_at':0,'remembered':False}
  with patch('session_vault.save') as save,patch.object(accounts,'_request',side_effect=[{'access_token':'new','refresh_token':'newr'},{'id':'u','email':'test@example.org'}]):
   self.assertTrue(accounts.account('status')['signed_in']);save.assert_not_called()
