import unittest
from unittest.mock import patch
import accounts
class AccountsTests(unittest.TestCase):
 def setUp(self):
  self.vault=patch('accounts._forget');self.vault.start();self.addCleanup(self.vault.stop)
 def tearDown(self):accounts._session=None
 def test_only_credentials_uploaded_and_token_not_returned(self):
  calls=[]
  def fake(path,body=None,token=None):
   calls.append((path,body))
   return {'email':'test@example.org','id':'test'} if path.endswith('/user') else {'access_token':'PRIVATE_TOKEN'}
  with patch.object(accounts,'_request',fake):
   result=accounts.account('signin',{'email':'test@example.org','password':'synthetic-password','text':'SECRET_WRITING','eeg':[123],'embedding':[456]})
   self.assertEqual(calls[0][1],{'email':'test@example.org','password':'synthetic-password'})
   self.assertNotIn('PRIVATE_TOKEN',str(result));self.assertTrue(result['signed_in'])
 def test_signout_clears_local_session_even_if_network_fails(self):
  accounts._session={'token':'dummy','email':'test@example.org'}
  with patch.object(accounts,'_request',side_effect=ValueError()):self.assertFalse(accounts.account('signout')['signed_in'])
  self.assertIsNone(accounts._session)
 def test_no_arbitrary_endpoint(self):
  with self.assertRaises(ValueError):accounts._request('/rest/v1/private_records',{'text':'secret'})
 def test_invalid_credentials_do_not_contact_network(self):
  with patch.object(accounts,'_request') as request:
   with self.assertRaises(ValueError):accounts.account('signup',{'email':'invalid','password':'123'})
   request.assert_not_called()
 def test_delete_requires_explicit_confirmation(self):
  accounts._session={'token':'dummy','email':'test@example.org'}
  with patch.object(accounts,'_request') as request:
   with self.assertRaises(ValueError):accounts.account('delete',{'confirmation':'no'})
   request.assert_not_called()
 def test_delete_only_sends_empty_body_with_current_token(self):
  accounts._session={'token':'dummy','email':'test@example.org'}
  with patch.object(accounts,'_request',return_value={}) as request:
   accounts.account('delete',{'confirmation':'DELETE','user_id':'someone-else'})
   request.assert_called_once_with('/rest/v1/rpc/bandstand_delete_own_account',{},'dummy')
   self.assertIsNone(accounts._session)
 def test_recovery_only_sends_email(self):
  with patch.object(accounts,'_request',return_value={}) as request:
   result=accounts.account('recover',{'email':'test@example.org','redirect_to':'https://evil.example','text':'private'})
   request.assert_called_once_with('/auth/v1/recover',{'email':'test@example.org'})
   self.assertIn('If this address',result['message'])
 def test_reset_validates_recovery_type_before_network(self):
  for code in ('123','https://evil.example/auth/v1/verify?token=abc&type=recovery',accounts.URL+'/auth/v1/verify?token=abc&type=signup'):
   with patch.object(accounts,'_request') as request:
    with self.assertRaises(ValueError):accounts.account('reset',{'email':'test@example.org','password':'synthetic-password','code':code})
    request.assert_not_called()
 def test_recovery_cannot_reset_another_email(self):
  with patch.object(accounts,'_request',side_effect=[{'access_token':'synthetic'},{'email':'other@example.org'},{}]) as request:
   with self.assertRaises(ValueError):accounts.account('reset',{'email':'test@example.org','password':'synthetic-password','code':'123456'})
   self.assertFalse(any(c.kwargs.get('method')=='PUT' for c in request.call_args_list))
 def test_reset_only_sends_password_after_recovery_verification(self):
  for code in ('123456',accounts.URL+'/auth/v1/verify?token=abc&type=recovery'):
   with patch.object(accounts,'_request',side_effect=[{'access_token':'synthetic'},{'email':'test@example.org'},{},{}]) as request:
    result=accounts.account('reset',{'email':'test@example.org','password':'synthetic-password','code':code,'text':'private'})
    self.assertEqual(request.call_args_list[2].args,('/auth/v1/user',{'password':'synthetic-password'},'synthetic'))
    self.assertEqual(request.call_args_list[2].kwargs,{'method':'PUT'})
    self.assertFalse(result['signed_in']);self.assertNotIn('synthetic',str(result))
 def test_confirmation_does_not_update_password_or_expose_session(self):
  with patch.object(accounts,'_request',side_effect=[{'access_token':'synthetic'},{'email':'test@example.org'},{}]) as request:
   result=accounts.account('confirm',{'email':'test@example.org','code':accounts.URL+'/auth/v1/verify?token=abc&type=signup','password':'ignored'})
   self.assertFalse(any(c.kwargs.get('method')=='PUT' for c in request.call_args_list))
   self.assertNotIn('synthetic',str(result));self.assertIsNone(accounts._session)
 def test_recovery_link_cannot_be_used_for_confirmation(self):
  with patch.object(accounts,'_request') as request:
   with self.assertRaises(ValueError):accounts.account('confirm',{'email':'test@example.org','code':accounts.URL+'/auth/v1/verify?token=abc&type=recovery'})
   request.assert_not_called()
 def test_preferences_uploads_only_explicit_choices(self):
  from enrollment import POLICY_VERSION
  accounts._session={'token':'synthetic','email':'test@example.org'}
  with patch.object(accounts,'_request',return_value={}) as request:
   result=accounts.account('preferences',{'policy_version':POLICY_VERSION,'acknowledged':True,'erp_sharing_requested':True,'decoder_interest_requested':True,'text':'PRIVATE','eeg':[1],'embedding':[2],'decoder_upload_enabled':True})
   payload=request.call_args.args[1]['data']['bandstand_preferences']
   self.assertEqual(set(payload),{'policy_version','acknowledged','erp_sharing_requested','decoder_interest_requested','sharing_choices_reviewed','erp_policy'})
   self.assertTrue(result['saved']);self.assertNotIn('PRIVATE',str(request.call_args))
 def test_preferences_require_login_and_acknowledgment(self):
  with patch.object(accounts,'_request') as request:
   with self.assertRaises(ValueError):accounts.account('preferences',{})
   accounts._session={'token':'synthetic','email':'test@example.org'}
   with self.assertRaises(ValueError):accounts.account('preferences',{'acknowledged':False})
   request.assert_not_called()

 def test_signup_requires_current_privacy_acknowledgment(self):
  from enrollment import POLICY_VERSION
  for extra in ({},{'acknowledged':True,'policy_version':'old'},{'acknowledged':False,'policy_version':POLICY_VERSION}):
   with patch.object(accounts,'_request') as request:
    with self.assertRaises(ValueError):accounts.account('signup',dict(email='test@example.org',password='synthetic-password',**extra))
    request.assert_not_called()
  with patch.object(accounts,'_request',return_value={}) as request:
   accounts.account('signup',{'email':'test@example.org','password':'synthetic-password','acknowledged':True,'policy_version':POLICY_VERSION})
   self.assertEqual(request.call_args.args[0],'/auth/v1/signup')
