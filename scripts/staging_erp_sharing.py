"""Milestone-two acceptance: dependable ERP sharing against the LOCAL Supabase stack.

Runs the real accounts.py outbox and the real database RPCs with two synthetic accounts and synthetic ERP
recordings written to the throwaway BANDSTAND_DATA_DIR (marked as test fixtures; text canaries planted in
fields that must never leave the device). Reuses staging_accounts.py helpers and output format.
  BANDSTAND_DATA_DIR=<empty throwaway dir> python scripts/staging_erp_sharing.py"""
import json,secrets,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import staging_accounts as sa
from staging_accounts import app,expect,raw,db,quote,check
import accounts,erp_outbox,erp_sharing
from enrollment import POLICY_VERSION
from private_storage import DATA_ROOT
if not sa.LOCAL:sys.exit('This harness needs the local stack (direct database access for row checks and quotas).')
CANARY='CANARY-'+secrets.token_hex(6)
TIMES=[round(-.2+i/256,6) for i in range(257)]

def fixture(trials=4,protocol='oddball',end='completed'):
 """A synthetic finished ERP recording in the shape engine.py writes. 'live' is required by the sharing gate;
 the folder lives only in the throwaway data directory and is labelled as a test fixture."""
 ident=str(uuid.uuid4());d=DATA_ROOT/ident;d.mkdir()
 (d/'session.json').write_text(json.dumps({'id':ident,'mode':'erp','source':'live','protocol':protocol,'running':False,'end_reason':end,'title':'SYNTHETIC TEST FIXTURE '+CANARY,
  'channels':['TP9','TP10'],'window':[.3,.5],'trials_planned':trials,'notes':CANARY}))
 (d/'trials.json').write_text(json.dumps([{'index':i,'condition_index':i%2,'condition':CANARY,'onset':1e9+i,'times':TIMES,
  'channel_trials':{c:{'accepted':i%3!=0,'reasons':[] if i%3 else ['probable blink',CANARY],'wave':[float((i+k)%7) for k in range(257)] if i%3 else None} for c in ('TP9','TP10')}} for i in range(trials)]))
 return ident,erp_sharing.payload(ident)[0]

def rows(user):return int(db(f"select count(*) from public.bandstand_erp_recordings where user_id={quote(user)}"))
def outbox(rid):return next((i for i in erp_outbox.items() if i['id']==rid),None)

def main():
 run=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(2);mail=sa.Mailpit()
 email={k:f'bandstand-erp-{k}-{run}@example.test' for k in 'ab'};pw={k:sa.secret('Synthetic-'+secrets.token_urlsafe(15)) for k in 'ab'}
 try:sa.session_vault.clear()
 except ValueError:pass
 print(f'Backend: {sa.B["name"]} {sa.B["url"]}  run {run}',flush=True)
 # Account A through the app; B directly. Both confirmed.
 app('signup',{'email':email['a'],'password':pw['a'],'policy_version':POLICY_VERSION,'acknowledged':True})
 app('confirm',{'email':email['a'],'code':mail.code(email['a'],'confirmation')['code']})
 app('signin',{'email':email['a'],'password':pw['a']});A=accounts._session['user_id']
 B=sa.raw_account(email['b'],pw['b'],mail)['id']
 prefs={'policy_version':POLICY_VERSION,'acknowledged':True,'erp_policy':'erp-sharing-v1','erp_auto_share':True}
 state={}

 @check('Q01','erp','Opted out: a finished recording is not queued and nothing is uploaded')
 def _():
  app('preferences',{**prefs,'erp_sharing_requested':False});app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':False})
  s,_=fixture();r=app('erp-enqueue',{'recording_id':s});expect(r['queued'] is False,r);accounts._outbox_pass()
  expect(rows(A)==0,'rows uploaded');return 'not queued; 0 server rows'
 @check('Q02','erp','Opted in: the recording is queued, uploaded in the background, and listed; no text leaves the device')
 def _():
  app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':True});app('preferences',{**prefs,'erp_sharing_requested':True})
  s,rid=fixture();state['s1'],state['r1']=s,rid
  r=app('erp-enqueue',{'recording_id':s});expect(r['queued'] and r['pending']==1,r)
  expect(accounts._outbox_pass()==1,'not uploaded');expect(outbox(rid)['state']=='uploaded',outbox(rid))
  listed=app('erp-list',{});expect([x['recording_id'] for x in listed]==[rid],listed)
  stored=db(f"select payload::text from public.bandstand_erp_recordings where recording_id={quote(rid)}")
  expect(CANARY not in stored and 'onset' not in stored and 'SYNTHETIC' not in stored,'text reached the server')
  return f'uploaded and listed; stored payload has no canary, title, labels or onsets ({len(stored)} bytes)'
 @check('Q03','erp','Duplicates: re-queueing and re-sending the same recording store one row')
 def _():
  app('erp-enqueue',{'recording_id':state['s1']});accounts._outbox_pass()
  ident,recording=erp_sharing.payload(state['s1']);c,_=raw('POST','/rest/v1/rpc/bandstand_upload_erp',{'recording_id':ident,'recording':recording},accounts._session['token'])
  expect(c in (200,204),c);expect(rows(A)==1,rows(A));return 'one server row after re-queue and direct re-send'
 @check('Q04','erp','Withdrawal before upload: the queued recording never leaves')
 def _():
  s,rid=fixture();app('erp-enqueue',{'recording_id':s});app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':False})
  expect(outbox(rid)['state']=='withdrawn',outbox(rid));accounts._outbox_pass();expect(rows(A)==1,rows(A))
  return 'item withdrawn locally at once; server rows unchanged'
 @check('Q05','erp','Withdrawal during retry: a recording waiting out a network failure is not sent after consent is turned off')
 def _():
  app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':True});s,rid=fixture();app('erp-enqueue',{'recording_id':s})
  url=accounts.URL;accounts.URL='http://127.0.0.1:9'
  try:accounts._outbox_pass()
  finally:accounts.URL=url
  item=outbox(rid);expect(item['state']=='pending' and item['attempts']==0,item)  # consent check failed first: nothing attempted
  app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':False});accounts._outbox_pass(now=time.time()+4000)
  expect(outbox(rid)['state']=='withdrawn' and rows(A)==1,(outbox(rid),rows(A)));return 'network loss kept it pending; withdrawal then cancelled it; never uploaded'
 @check('Q06','erp','Network failure during upload backs off and later succeeds')
 def _():
  app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':True});s,rid=fixture();app('erp-enqueue',{'recording_id':s})
  real=accounts._request
  def flaky(path,*a,**k):
   if path.endswith('bandstand_upload_erp'):raise ValueError('Account service unavailable. Local recording remains available.')
   return real(path,*a,**k)
  accounts._request=flaky
  try:accounts._outbox_pass()
  finally:accounts._request=real
  item=outbox(rid);expect(item['state']=='pending' and item['attempts']==1 and item['next_at']>time.time()+20,item)
  expect(accounts._outbox_pass()==0,'retried too early');expect(accounts._outbox_pass(now=item['next_at']+1)==1,'retry did not upload')
  state['r6']=rid;return f'attempt 1 failed, retry scheduled {erp_outbox.backoff(1)} s later, then uploaded'
 @check('Q07','erp','Account switch: another account signed in on this computer never sends the first account\'s recording')
 def _():
  s,rid=fixture();app('erp-enqueue',{'recording_id':s});before=rows(A)
  app('signout');accounts.account('signin',{'email':email['b'],'password':pw['b']});expect(accounts._session['user_id']==B,'not B')
  accounts._outbox_pass(now=time.time()+4000)
  expect(rows(B)==0 and rows(A)==before and outbox(rid)['state']=='pending',(rows(B),rows(A),outbox(rid)))
  expect(app('erp-outbox',{})['held_for_other_account']>=1,'not reported as held')
  app('signout');app('signin',{'email':email['a'],'password':pw['a']});accounts._outbox_pass(now=time.time()+4000)
  expect(rows(A)==before+1 and rows(B)==0,(rows(A),rows(B)));return 'held while B was signed in (0 rows for B); uploaded under A after A returned'
 @check('Q08','erp','Restart during an upload: the interrupted item resumes and is stored once')
 def _():
  s,rid=fixture();app('erp-enqueue',{'recording_id':s});item=outbox(rid);item['state']='uploading';erp_outbox._write(item);before=rows(A)
  erp_outbox.recover();expect(outbox(rid)['state']=='pending','not recovered');accounts._outbox_pass();expect(rows(A)==before+1,rows(A))
  return 'uploading → pending on restart → uploaded once'
 bad=[]
 @check('Q09','erp','The database refuses malformed, oversized and text-bearing payloads (v1 and v2)')
 def _():
  token=accounts._session['token'];ident,good=erp_sharing.payload(state['s1']);_,v2=erp_sharing.payload(state['s1'],'bandstand-erp-v2')
  def mutate(base,fn):x=json.loads(json.dumps(base));fn(x);return x
  cases={'extra top-level text field':mutate(good,lambda x:x.update(note=CANARY)),'text in a waveform':mutate(good,lambda x:x['trials'][1]['channels']['TP9']['wave'].__setitem__(0,CANARY)),
   'waveform length mismatch':mutate(good,lambda x:x['trials'][1]['channels']['TP9']['wave'].pop()),'1025-sample arrays':mutate(good,lambda x:[t.update(times=[0]*1025) for t in x['trials']]),
   'unknown channel':mutate(good,lambda x:x['trials'][0]['channels'].update(Fz={'accepted':True,'wave':None})),'condition 2':mutate(good,lambda x:x['trials'][0].update(condition=2)),
   'unknown protocol':mutate(good,lambda x:x.update(protocol='custom')),'10001 trials':mutate(good,lambda x:x.update(trials=[x['trials'][0]]*10001)),
   'v2 unknown rejection category':mutate(v2,lambda x:x['trials'][0]['channels']['TP9'].update(rejection=[CANARY])),'v2 extra recording key':mutate(v2,lambda x:x['recording'].update(title=CANARY)),
   'v2 presented count mismatch':mutate(v2,lambda x:x['recording'].update(trials_presented=99)),'v2 text app version':mutate(v2,lambda x:x['recording'].update(app_version=CANARY)),
   'v2 field on a v1 payload':mutate(good,lambda x:x.update(recording=v2['recording']))}
  out={k:raw('POST','/rest/v1/rpc/bandstand_upload_erp',{'recording_id':str(uuid.uuid4()),'recording':v},token)[0] for k,v in cases.items()}
  bad.extend(k for k,c in out.items() if c<400);expect(not bad,bad)
  c,_=raw('POST','/rest/v1/rpc/bandstand_upload_erp',{'recording_id':str(uuid.uuid4()),'recording':v2},token);expect(c in (200,204),f'valid v2 refused: {c}')
  stored=db("select count(*) from public.bandstand_erp_recordings where payload::text like "+quote('%'+CANARY+'%'));expect(stored=='0',stored)
  return f'{len(cases)} bad payloads refused; a valid v2 payload accepted; no canary stored'
 @check('Q10','erp','Without server-side consent the database refuses uploads even from the app')
 def _():
  app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':False});ident,good=erp_sharing.payload(state['s1'])
  c,_=raw('POST','/rest/v1/rpc/bandstand_upload_erp',{'recording_id':str(uuid.uuid4()),'recording':good},accounts._session['token']);expect(c>=400,c)
  app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':True});return f'HTTP {c}'
 @check('Q11','erp','Provisional quota: the 101st new recording in a day is refused; re-sending a stored one still succeeds')
 def _():
  db(f"insert into public.bandstand_erp_recordings(user_id,recording_id,payload) select {quote(A)},gen_random_uuid(),'{{}}'::jsonb from generate_series(1,100-{rows(A)})")
  token=accounts._session['token'];ident,good=erp_sharing.payload(state['s1'])
  c,_=raw('POST','/rest/v1/rpc/bandstand_upload_erp',{'recording_id':str(uuid.uuid4()),'recording':good},token);expect(c>=400,f'new upload over quota: {c}')
  c2,_=raw('POST','/rest/v1/rpc/bandstand_upload_erp',{'recording_id':ident,'recording':good},token);expect(c2 in (200,204),f'idempotent resend refused: {c2}')
  db(f"delete from public.bandstand_erp_recordings where user_id={quote(A)} and payload='{{}}'::jsonb");return f'new upload HTTP {c}; re-send of stored recording HTTP {c2}'
 @check('Q12','erp','Validation cost of the largest realistic recording stays inside the API timeout')
 def _():
  s,_=fixture(trials=1000);ident,big=erp_sharing.payload(s);size=len(json.dumps(big));start=time.time()
  c,_=raw('POST','/rest/v1/rpc/bandstand_upload_erp',{'recording_id':ident,'recording':big},accounts._session['token']);took=time.time()-start
  expect(c in (200,204),c);expect(took<8,f'{took:.1f}s');return f'1000 trials x 2 channels x 257 samples ({size/1e6:.1f} MB): accepted in {took:.1f} s'
 @check('Q13','erp','Deleting the account removes its shared rows and its local queue')
 def _():
  s,rid=fixture();app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':False});app('erp-consent',{'sharing_policy':'erp-sharing-v1','allow':True})
  app('erp-enqueue',{'recording_id':s});app('delete',{'confirmation':'DELETE'})
  expect(rows(A)==0,rows(A));expect(not any(i['user']==A for i in erp_outbox.items()),'queue kept');return 'server rows 0; local queue entries 0'
 out=sa.ROOT/'build/acceptance';out.mkdir(parents=True,exist_ok=True)
 lines=['| ID | Area | Check | Outcome | Level | Evidence |','|---|---|---|---|---|---|']+[f"| {r['id']} | {r['area']} | {r['check']} | {r['outcome']} | {r['level']} | {r['evidence'].replace('|','/')} |" for r in sa.RESULTS]
 (out/f'erp-{run}.md').write_text(sa.redact(f"# ERP sharing acceptance run {run}\n\nBackend: {sa.B['name']} ({sa.B['url']})\n\n"+'\n'.join(lines)+'\n'))
 (out/f'erp-{run}.json').write_text(sa.redact(json.dumps({'run':run,'results':sa.RESULTS},indent=2)))
 counts={o:sum(r['outcome']==o for r in sa.RESULTS) for o in ('pass','fail','not run')};print(json.dumps(counts),'->',out/f'erp-{run}.md')
 sys.exit(1 if counts['fail'] else 0)

if __name__=='__main__':main()
