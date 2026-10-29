import os
import json,stat,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import accounts,erp_outbox
ID=str(uuid.uuid4())
class OutboxTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  p=patch.object(erp_outbox,'ROOT',Path(self.temp.name)/'erp-outbox');p.start();self.addCleanup(p.stop)
  self.uploads=[]
 def upload(self,item):self.uploads.append(item['id'])
 def test_enqueue_is_idempotent_private_and_stores_no_payload(self):
  erp_outbox.enqueue(ID,'session-a','user-a','erp-sharing-v1',now=1);erp_outbox.enqueue(ID,'session-b','user-b','erp-sharing-v1',now=2)
  [item]=erp_outbox.items();self.assertEqual((item['user'],item['session'],item['state']),('user-a','session-a','pending'))
  self.assertEqual(set(item),{'id','session','user','policy','state','attempts','next_at','created','updated','error'})
  if os.name!='nt':self.assertEqual(stat.S_IMODE((erp_outbox.ROOT/f'{ID}.json').stat().st_mode),0o600)
 def test_uploads_only_for_the_consenting_account(self):
  erp_outbox.enqueue(ID,'s','user-a','erp-sharing-v1',now=0)
  self.assertEqual(erp_outbox.process('user-b',lambda:True,self.upload,now=1),0);self.assertEqual(self.uploads,[])
  self.assertEqual(erp_outbox.summary('user-b')['held_for_other_account'],1)
  self.assertEqual(erp_outbox.process('user-a',lambda:True,self.upload,now=1),1);self.assertEqual(self.uploads,[ID])
  self.assertEqual(erp_outbox.items()[0]['state'],'uploaded')
 def test_server_consent_off_withdraws_without_uploading(self):
  erp_outbox.enqueue(ID,'s','user-a','erp-sharing-v1',now=0)
  erp_outbox.process('user-a',lambda:False,self.upload,now=1)
  self.assertEqual(self.uploads,[]);self.assertEqual(erp_outbox.items()[0]['state'],'withdrawn')
 def test_unreachable_consent_check_changes_nothing(self):
  erp_outbox.enqueue(ID,'s','user-a','erp-sharing-v1',now=0)
  def down():raise erp_outbox.TransientError()
  erp_outbox.process('user-a',down,self.upload,now=1);item=erp_outbox.items()[0]
  self.assertEqual((item['state'],item['attempts']),('pending',0));self.assertEqual(self.uploads,[])
 def test_transient_failures_back_off_then_give_up(self):
  erp_outbox.enqueue(ID,'s','user-a','erp-sharing-v1',now=0)
  def flaky(item):raise erp_outbox.TransientError()
  now=0
  for attempt in range(1,erp_outbox.MAX_ATTEMPTS):
   erp_outbox.process('user-a',lambda:True,flaky,now=now);item=erp_outbox.items()[0]
   self.assertEqual((item['state'],item['attempts']),('pending',attempt));self.assertEqual(item['next_at'],now+erp_outbox.backoff(attempt))
   self.assertEqual(erp_outbox.process('user-a',lambda:True,self.upload,now=item['next_at']-1),0)  # not due yet
   now=item['next_at']
  erp_outbox.process('user-a',lambda:True,flaky,now=now);self.assertEqual(erp_outbox.items()[0]['state'],'failed')
  self.assertLessEqual(max(erp_outbox.backoff(n) for n in range(1,20)),3600)
 def test_refused_recording_fails_without_retry(self):
  erp_outbox.enqueue(ID,'s','user-a','erp-sharing-v1',now=0)
  def refused(item):raise ValueError('The server refused this recording.')
  erp_outbox.process('user-a',lambda:True,refused,now=1);self.assertEqual(erp_outbox.items()[0]['state'],'failed')
 def test_recover_withdraw_retry_and_forget(self):
  erp_outbox.enqueue(ID,'s','user-a','erp-sharing-v1',now=0);item=erp_outbox.items()[0];item['state']='uploading';erp_outbox._write(item)
  erp_outbox.recover(now=5);self.assertEqual(erp_outbox.items()[0]['state'],'pending')
  item=erp_outbox.items()[0];item['state']='failed';erp_outbox._write(item)
  erp_outbox.retry('user-b');self.assertEqual(erp_outbox.items()[0]['state'],'failed')
  erp_outbox.retry('user-a');self.assertEqual(erp_outbox.items()[0]['state'],'pending')
  erp_outbox.withdraw('user-a');self.assertEqual(erp_outbox.items()[0]['state'],'withdrawn')
  erp_outbox.forget('user-a');self.assertEqual(erp_outbox.items(),[])
 def test_rejects_non_uuid_item_ids(self):
  with self.assertRaises(ValueError):erp_outbox.enqueue('../../escape','s','u','p')

class AccountOutboxTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  p=patch.object(erp_outbox,'ROOT',Path(self.temp.name)/'erp-outbox');p.start();self.addCleanup(p.stop)
  for name in ('_restore','_forget'):q=patch(f'accounts.{name}');q.start();self.addCleanup(q.stop)
  accounts._session={'token':'token-a','email':'a@example.org','user_id':'user-a','preferences':{'erp_auto_share':True,'erp_sharing_requested':True}}
  self.addCleanup(lambda:setattr(accounts,'_session',None))
 def test_withdrawal_stops_queue_even_if_server_unreachable(self):
  erp_outbox.enqueue(ID,'s','user-a','erp-sharing-v1')
  with patch.object(accounts,'_request',side_effect=ValueError('down')),self.assertRaises(ValueError):
   accounts.account('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':False})
  self.assertEqual(erp_outbox.items()[0]['state'],'withdrawn')
 def test_opting_in_does_not_backfill_earlier_recordings(self):
  with patch.object(accounts,'_request',return_value={}):accounts.account('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':True})
  self.assertEqual(erp_outbox.items(),[])
 def test_enqueue_binds_signed_in_account_and_respects_opt_out(self):
  with patch('erp_sharing.payload',return_value=(ID,{})):
   r=accounts.account('erp-enqueue',{'recording_id':'abc123'})
   self.assertTrue(r['queued']);self.assertEqual(erp_outbox.items()[0]['user'],'user-a')
   erp_outbox.forget('user-a');accounts._session['preferences']={'erp_auto_share':True,'erp_sharing_requested':False}
   self.assertFalse(accounts.account('erp-enqueue',{'recording_id':'abc123'})['queued']);self.assertEqual(erp_outbox.items(),[])
 def test_account_switch_mid_pass_never_uploads_with_another_token(self):
  erp_outbox.enqueue(ID,'abc123','user-a','erp-sharing-v1',now=0);calls=[]
  def request(path,body=None,token=None,method=None):
   calls.append((path,token))
   if path.endswith('bandstand_sharing_status'):
    accounts._session={'token':'token-b','email':'b@example.org','user_id':'user-b','preferences':{}}  # B signs in
    return {'erp_sharing':True}
   return {}
  with patch.object(accounts,'_request',side_effect=request),patch('erp_sharing.payload',return_value=(ID,{})):accounts._outbox_pass(now=1)
  self.assertFalse(any(p.endswith('bandstand_upload_erp') for p,_ in calls));self.assertEqual(erp_outbox.items()[0]['state'],'pending')
 def test_pass_uploads_with_the_queuing_accounts_token(self):
  erp_outbox.enqueue(ID,'abc123','user-a','erp-sharing-v1',now=0)
  with patch.object(accounts,'_request',return_value={'erp_sharing':True}) as request,patch('erp_sharing.payload',return_value=(ID,{'schema':'bandstand-erp-v1'})):
   self.assertEqual(accounts._outbox_pass(now=1),1)
  upload=[c for c in request.call_args_list if c.args[0].endswith('bandstand_upload_erp')][0]
  self.assertEqual(upload.args[2],'token-a');self.assertEqual(upload.args[1]['recording_id'],ID)
 def test_delete_account_forgets_its_queue(self):
  erp_outbox.enqueue(ID,'s','user-a','erp-sharing-v1')
  with patch.object(accounts,'_request',return_value={}):accounts.account('delete',{'confirmation':'DELETE'})
  self.assertEqual(erp_outbox.items(),[])
