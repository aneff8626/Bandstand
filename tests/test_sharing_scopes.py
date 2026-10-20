import unittest
from sharing_policy import choices, POLICY_VERSION
class SharingScopeTests(unittest.TestCase):
 def body(self,scope):return {'policy_version':POLICY_VERSION,'acknowledged':True,'sharing_scope':scope,'sharing_choices_reviewed':True}
 def test_non_typing_does_not_authorize_decoder(self):
  result=choices(self.body('non_typing'));self.assertTrue(result['erp_sharing_requested']);self.assertFalse(result['decoder_interest_requested'])
 def test_none_withdraws(self):
  result=choices(self.body('none'));self.assertFalse(result['erp_sharing_requested']);self.assertFalse(result['erp_auto_share'])
 def test_explicit_typing_choice_is_sufficient(self):
  result=choices(self.body('including_typing'))
  self.assertTrue(result['typing_risk_acknowledged'])
  self.assertTrue(result['decoder_interest_requested']);self.assertNotIn('decoder_upload_enabled',result)
 def test_legacy_consent_is_not_upgraded(self):
  with self.assertRaises(ValueError):choices({'policy_version':POLICY_VERSION,'acknowledged':True,'erp_sharing_requested':True})
 def test_no_private_content_in_preferences(self):
  body=self.body('non_typing');body.update(text='PRIVATE',embedding=[1],eeg=[2],decoder_upload_enabled=True)
  result=choices(body)
  for name in ('text','embedding','eeg','decoder_upload_enabled'):self.assertNotIn(name,result)
