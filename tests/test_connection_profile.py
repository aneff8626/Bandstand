import unittest,threading
from unittest.mock import Mock,patch
from engine import Engine
import accounts
class ConnectionProfileTests(unittest.TestCase):
 def test_disconnect_stops_helper_and_blocks_reconnect_until_requested(self):
  e=Engine.__new__(Engine);e.lock=threading.RLock();e.session=None;e.typing=Mock(running=False);e.developer=Mock();e.developer.status.return_value={};e.bridge=Mock();e.bridge.poll.return_value=None;e.bridge_enabled=threading.Event();e.bridge_enabled.set()
  e.bluetooth_connection(False)
  e.bridge.terminate.assert_called_once();self.assertFalse(e.bridge_enabled.is_set());self.assertEqual(e.status['state'],'disconnected')
  e.bluetooth_connection(True);self.assertTrue(e.bridge_enabled.is_set())
 def test_profile_only_sends_display_name(self):
  with patch.object(accounts,'_session',{'token':'synthetic','email':'test@example.org'}),patch.object(accounts,'_restore'),patch.object(accounts,'_request') as request:
   r=accounts.account('profile',{'display_name':'Andrew','text':'DO NOT SEND'})
   request.assert_called_once_with('/auth/v1/user',{'data':{'display_name':'Andrew'}},'synthetic',method='PUT')
   self.assertEqual(r['display_name'],'Andrew');self.assertNotIn('token',r)
   with self.assertRaises(ValueError):accounts.account('profile',{'display_name':'a'*41})
