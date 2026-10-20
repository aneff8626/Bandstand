"""Milestone-one acceptance: accounts, consent and record isolation against a NON-production Supabase project.

Drives the real accounts.py flows plus direct REST probes, then writes a results matrix to
build/acceptance/. It refuses to run against production. It prints no passwords, tokens or email codes.

Local stack (Docker, `supabase start`), email read from the stack's Mailpit catcher:
  backend.json -> {"name":"development","url":"http://127.0.0.1:54321","publishable_key":"<local publishable key>"}
  BANDSTAND_DATA_DIR=<empty throwaway dir> python scripts/staging_accounts.py --mail mailpit
Cloud development/staging project, codes typed in by the operator from a real inbox:
  BANDSTAND_DATA_DIR=<empty throwaway dir> python scripts/staging_accounts.py --mail prompt --email-a <addr> --email-b <addr> --email-c <addr>
Checks that need direct database access (backdating a code, row counts, stopping the mail server) run
only on the local stack and are reported as not run elsewhere."""
import argparse,base64,hashlib,hmac,json,os,re,secrets,shutil,socket,subprocess,sys,threading,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
if not os.environ.get('BANDSTAND_DATA_DIR'):sys.exit('Set BANDSTAND_DATA_DIR to an empty throwaway directory; never run acceptance against real participant data.')
import accounts,session_vault
from enrollment import POLICY_VERSION
from private_storage import DATA_ROOT
B=accounts.BACKEND
if B['name']=='production':sys.exit('Refusing to run: accounts.py targets production. Add a development or staging backend.json first.')
LOCAL=urllib.parse.urlsplit(B['url']).hostname in ('127.0.0.1','localhost')
SECRETS=set();RESULTS=[];MESSAGES=[]
PROJECT=re.search(r'^project_id\s*=\s*"([^"]+)"',(ROOT/'supabase/config.toml').read_text(),re.M).group(1)
DOCKER=shutil.which('docker') or str(Path.home()/'.docker/bin/docker')

def secret(value):
 if value:SECRETS.add(value)
 return value
def redact(text):
 text=str(text)
 for s in sorted(SECRETS,key=len,reverse=True):text=text.replace(s,'<redacted>')
 return re.sub(r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','<jwt>',text)

def check(ident,area,name,local_only=False):
 def wrap(fn):
  if local_only and not LOCAL:
   RESULTS.append({'id':ident,'area':area,'check':name,'outcome':'not run','level':'needs local stack','evidence':'Requires direct database or container access.'});return fn
  try:
   evidence=fn() or '';outcome='pass'
   if isinstance(evidence,tuple):outcome,evidence=evidence  # ('observed', ...) documents behavior without a verdict
   RESULTS.append({'id':ident,'area':area,'check':name,'outcome':outcome,'level':'local stack' if LOCAL else B['name']+' cloud project','evidence':redact(evidence)})
  except Exception as e:
   RESULTS.append({'id':ident,'area':area,'check':name,'outcome':'fail','level':'local stack' if LOCAL else B['name']+' cloud project','evidence':redact(f'{type(e).__name__}: {e}')})
  print(f"{RESULTS[-1]['outcome']:>7}  {ident} {name}",flush=True)
  return fn
 return wrap

def expect(condition,message):
 if not condition:raise AssertionError(message)

def app(action,body=None):
 """Call the real account handler; record user-visible messages for the hygiene check."""
 try:
  result=accounts.account(action,body);MESSAGES.append(json.dumps(result));return result
 except ValueError as e:
  MESSAGES.append(str(e));raise

def app_error(action,body=None):
 try:app(action,body)
 except ValueError as e:return e
 raise AssertionError(f'{action} unexpectedly succeeded')

def raw(method,path,body=None,token=None,apikey=True):
 headers={'Content-Type':'application/json'}
 if apikey:headers['apikey']=B['publishable_key']
 if token:headers['Authorization']='Bearer '+token
 req=urllib.request.Request(B['url']+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
 try:
  with urllib.request.urlopen(req,timeout=20) as r:
   data=r.read();return r.status,(json.loads(data) if data else None)
 except urllib.error.HTTPError as e:
  data=e.read()
  try:return e.code,json.loads(data)
  except ValueError:return e.code,None

def db(sql):
 out=subprocess.run([DOCKER,'exec','-i',f'supabase_db_{PROJECT}','psql','-U','postgres','-t','-A','-q','-c',sql],capture_output=True,text=True,timeout=60)
 if out.returncode:raise RuntimeError('database query failed: '+out.stderr.strip()[:300])
 return out.stdout.strip()
def quote(s):return "'"+s.replace("'","''")+"'"

class Mailpit:
 base=B['url'].replace(':54321',':54324')
 def __init__(self):self.seen=set()
 def code(self,to,kind,timeout=30):
  deadline=time.time()+timeout
  while time.time()<deadline:
   with urllib.request.urlopen(self.base+'/api/v1/search?'+urllib.parse.urlencode({'query':f'to:"{to}"'}),timeout=10) as r:messages=json.loads(r.read())['messages']
   for m in messages:
    if m['ID'] in self.seen:continue
    with urllib.request.urlopen(self.base+'/api/v1/message/'+m['ID'],timeout=10) as r:full=json.loads(r.read())
    self.seen.add(m['ID'])
    body=full.get('HTML','')+full.get('Text','')
    found=re.search(r'\b(\d{6,10})\b',re.sub(r'<[^>]+>',' ',body))
    expect(found,f'{kind} email has no numeric code')
    expect('{{' not in body,'email template left an unrendered placeholder')
    return {'code':secret(found.group(1)),'subject':m['Subject'],'body':body}
   time.sleep(0.5)
  raise AssertionError(f'no {kind} email arrived for the test address within {timeout}s')
 def none_since(self,to,wait=4):
  time.sleep(wait)
  with urllib.request.urlopen(self.base+'/api/v1/search?'+urllib.parse.urlencode({'query':f'to:"{to}"'}),timeout=10) as r:
   return not [m for m in json.loads(r.read())['messages'] if m['ID'] not in self.seen]

class Prompt:
 def code(self,to,kind,timeout=None):
  value=input(f'Enter the {kind} code emailed to {to} (or blank if none arrived): ').strip()
  expect(value,f'operator reported no {kind} email');return {'code':secret(value),'subject':'(operator-read)','body':''}
 def none_since(self,to,wait=0):return input(f'Did a NEW email arrive for {to}? [y/N] ').strip().lower()!='y'

def reopen_status():
 """A fresh process is the app being closed and reopened: it can only know the session through Keychain."""
 out=subprocess.run([sys.executable,'-c','import json,accounts;s=accounts.account("status");print(json.dumps({k:s[k] for k in ("signed_in","remembered","display_name","email","backend")}))'],cwd=ROOT,capture_output=True,text=True,timeout=60,env=os.environ)
 if out.returncode:raise RuntimeError('reopened app failed: '+redact(out.stderr)[-300:])
 return json.loads(out.stdout.strip().splitlines()[-1])

def password_grant(email,password):
 status,body=raw('POST','/auth/v1/token?grant_type=password',{'email':email,'password':password})
 expect(status==200,f'password sign-in returned {status}')
 return {'access':secret(body['access_token']),'refresh':secret(body['refresh_token']),'id':body['user']['id']}

def refresh_status(refresh):return raw('POST','/auth/v1/token?grant_type=refresh_token',{'refresh_token':refresh})[0]

def raw_account(email,password,mail):
 """Second test person, created directly against Auth (the app holds one session at a time)."""
 status,_=raw('POST','/auth/v1/signup',{'email':email,'password':password,'data':{'bandstand_privacy':{'policy_version':POLICY_VERSION,'acknowledged':True}}})
 expect(status==200,f'signup returned {status}')
 code=mail.code(email,'confirmation')['code']
 status,body=raw('POST','/auth/v1/verify',{'email':email,'token':code,'type':'email'})
 expect(status==200 and body.get('access_token'),f'verify returned {status}')
 return {'access':secret(body['access_token']),'refresh':secret(body['refresh_token']),'id':body['user']['id']}

def synthetic_erp(marker):
 times=[-0.2,0,0.2,0.4]
 return {'schema':'bandstand-erp-v1','protocol':'oddball','trials':[{'condition':c,'times':times,'channels':{ch:{'accepted':True,'wave':[marker,c,-marker,0.5]} for ch in ('TP9','TP10')}} for c in (0,1)]}

def mint(sub,exp,secret_key):
 enc=lambda d:base64.urlsafe_b64encode(json.dumps(d,separators=(',',':')).encode()).rstrip(b'=').decode()
 head=enc({'alg':'HS256','typ':'JWT'});claims=enc({'sub':sub,'role':'authenticated','aud':'authenticated','exp':int(exp),'iat':int(time.time())-7200})
 sig=base64.urlsafe_b64encode(hmac.new(secret_key.encode(),f'{head}.{claims}'.encode(),hashlib.sha256).digest()).rstrip(b'=').decode()
 return secret(f'{head}.{claims}.{sig}')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--mail',choices=('mailpit','prompt'),default='mailpit')
 for k in 'abcde':parser.add_argument('--email-'+k)
 args=parser.parse_args()
 if args.mail=='mailpit' and not LOCAL:sys.exit('Mailpit capture exists only on the local stack; use --mail prompt for a cloud project.')
 mail=Mailpit() if args.mail=='mailpit' else Prompt()
 run=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(2)
 email={k:(getattr(args,'email_'+k) or f'bandstand-{k}-{run}@example.test') for k in 'abcde'}
 if not LOCAL and not all(getattr(args,'email_'+k) for k in 'abc'):sys.exit('A cloud run needs --email-a, --email-b and --email-c inboxes you can read.')
 pw={k:secret('Synthetic-'+secrets.token_urlsafe(15)) for k in ('a','a2','b','c','d','e')}
 state={}
 print(f'Backend: {B["name"]} {B["url"]}  run {run}',flush=True)
 try:session_vault.clear()
 except ValueError:pass

 # Signup, confirmation and sign-in.
 @check('S01','signup','Signup with privacy acknowledgment asks the person to confirm by email')
 def _():
  r=app('signup',{'email':email['a'],'password':pw['a'],'display_name':'Synthetic A','policy_version':POLICY_VERSION,'acknowledged':True})
  expect(r['signed_in'] is False and 'Check your email' in r['message'],r);return r['message']
 @check('S02','signup','Confirmation email arrives with a visible code and Bandstand instructions')
 def _():
  m=mail.code(email['a'],'confirmation');state['code_a']=m['code']
  if args.mail=='mailpit':expect('Check your email' in m['body'] and 'Bandstand' in m['subject'],m['subject'])
  return f"subject: {m['subject']}; code length {len(m['code'])}"
 @check('S03','signup','Sign-in is refused before the email is confirmed')
 def _():
  e=app_error('signin',{'email':email['a'],'password':pw['a']});expect(getattr(e,'status',0)==400 and str(e)==accounts.AUTH_MESSAGES['email_not_confirmed'],(getattr(e,'status',0),str(e)));return str(e)
 @check('S04','signup','A wrong confirmation code is rejected')
 def _():
  wrong='000000' if state.get('code_a')!='000000' else '111111'
  e=app_error('confirm',{'email':email['a'],'code':wrong});expect(str(e)==accounts.AUTH_MESSAGES['otp_expired'],str(e));return f'{getattr(e,"status","")} {e}'
 @check('S05','signup','Confirmation accepts the code with the email typed in different letter case')
 def _():
  r=app('confirm',{'email':email['a'].upper(),'code':state['code_a']});expect('Email confirmed' in r['message'],r);return r['message']
 if not any(r['id']=='S05' and r['outcome']=='pass' for r in RESULTS):
  try:app('confirm',{'email':email['a'],'code':state['code_a']})
  except (ValueError,KeyError):pass
 @check('S06','signup','A used confirmation code cannot be reused')
 def _():
  e=app_error('confirm',{'email':email['a'],'code':state['code_a']});expect(str(e)==accounts.AUTH_MESSAGES['otp_expired'],str(e));return f'{getattr(e,"status","")} {e}'
 @check('S07','signin','A wrong password is refused with a generic message')
 def _():
  e=app_error('signin',{'email':email['a'],'password':pw['a']+'x'});expect(getattr(e,'status',0)==400 and str(e)==accounts.AUTH_MESSAGES['invalid_credentials'],(getattr(e,'status',0),str(e)));return str(e)
 @check('S08','signin','Sign-in with remember-me works with mixed-case email')
 def _():
  r=app('signin',{'email':email['a'].title(),'password':pw['a'],'remember':True})
  expect(r['signed_in'] and r['remembered'] and r['display_name']=='Synthetic A' and r['email']==email['a'],r);return 'signed in; remembered; display name restored'
 @check('S09','session','Remember-me stores only a refresh token in macOS Keychain')
 def _():
  stored=session_vault.load();expect(stored and stored==accounts._session['refresh_token'] and pw['a'] not in stored,'Keychain item missing or unexpected')
  secret(stored);return 'Keychain item present for this data directory; it equals the refresh token and holds no password'
 @check('S10','session','Closing and reopening the app restores the remembered identity')
 def _():
  s=reopen_status();expect(s['signed_in'] and s['remembered'] and s['email']==email['a'] and s['display_name']=='Synthetic A',s);return json.dumps({k:s[k] for k in ('signed_in','remembered','backend')})
 @check('S11','profile','Display-name change is saved to the account and survives a restart')
 def _():
  r=app('profile',{'display_name':'Synthetic A2'});expect(r['display_name']=='Synthetic A2',r)
  s=reopen_status();expect(s['display_name']=='Synthetic A2',s);return 'name updated in cloud metadata and visible after reopen'
 @check('S12','session','An expired access token is refreshed transparently with the stored refresh token')
 def _():
  before=accounts._session['token'];accounts._session['expires_at']=time.time()-5
  r=app('status');expect(r['signed_in'] and accounts._session['token']!=before,'session not refreshed')
  secret(accounts._session['token']);secret(accounts._session['refresh_token']);return 'new access token issued; still signed in'
 @check('S13','signup','Duplicate signup for an existing account does not create a second user or change the password')
 def _():
  # Auth either refuses (user_already_exists) or, on projects that obfuscate, answers like a new signup.
  try:r=app('signup',{'email':email['a'],'password':pw['a2'],'policy_version':POLICY_VERSION,'acknowledged':True});expect(r['signed_in'] is False,r);detail=[f"app message: {r['message']}"]
  except accounts.AccountError as e:
   expect(str(e)==accounts.AUTH_MESSAGES['user_already_exists'],str(e));detail=[f'HTTP {e.status}; app message: {e}']
  if LOCAL:
   count=db(f'select count(*) from auth.users where lower(email)=lower({quote(email["a"])})');expect(count=='1',f'{count} users');detail.append('users with this email: 1')
   detail.append('no new email sent' if mail.none_since(email['a'],wait=3) else 'an email WAS sent to the existing address')
  password_grant(email['a'],pw['a']);detail.append('original password still works')
  return '; '.join(detail)
 # Signup above clears the app session by design; sign back in for later steps.
 app('signin',{'email':email['a'],'password':pw['a'],'remember':True});state['a']=dict(accounts._session);secret(state['a']['token']);secret(state['a']['refresh_token'])

 # Anonymous, invalid and expired credentials; direct table access.
 rpcs={'bandstand_sharing_status':{},'bandstand_list_erp':{},'bandstand_set_erp_consent':{'allow_sharing':True},'bandstand_upload_erp':{'recording_id':'00000000-0000-4000-8000-000000000001','recording':synthetic_erp(1)},'bandstand_delete_erp':{},'bandstand_delete_own_account':{},'bandstand_valid_erp':{'recording':synthetic_erp(1)}}
 tables=('bandstand_consent','bandstand_erp_recordings','bandstand_model_releases')
 @check('A01','access','Anonymous callers cannot execute any Bandstand RPC')
 def _():
  codes={fn:raw('POST','/rest/v1/rpc/'+fn,body)[0] for fn,body in rpcs.items()}
  expect(all(c in (401,403,404) for c in codes.values()),codes);return json.dumps(codes)
 @check('A02','access','Publishable key is not an authorization boundary (user token without it)')
 def _():
  c=raw('POST','/rest/v1/rpc/bandstand_sharing_status',{},state['a']['token'],apikey=False)[0]
  return 'observed',f'HTTP {c} without the publishable key. Authorization rests on the user token and database grants, as the handoff states.'
 @check('A03','access','Direct table reads and writes are refused for anonymous and signed-in callers, and nothing changes')
 def _():
  # Well-formed requests, so permission is the only thing that can stop them (a 400 would prove nothing).
  uid=state['a']['user_id']
  probes={'bandstand_consent':('user_id=not.is.null',{'user_id':uid,'policy_version':'erp-sharing-v1','erp_sharing':True},{'erp_sharing':True}),
   'bandstand_erp_recordings':('user_id=not.is.null',{'user_id':uid,'recording_id':'00000000-0000-4000-8000-0000000000ff','payload':{}},{'payload':{}}),
   'bandstand_model_releases':('id=not.is.null',{'version':'synthetic','sha256':'0'*64,'storage_path':'synthetic','privacy_reviewed':True},{'privacy_reviewed':True})}
  before=db('select (select count(*) from public.bandstand_consent),(select count(*) from public.bandstand_erp_recordings),(select count(*) from public.bandstand_model_releases)') if LOCAL else None
  out={}
  for who,token in (('anon',None),('user',state['a']['token'])):
   for t,(where,row,change) in probes.items():
    for method,path,body in (('GET',f'/rest/v1/{t}?select=*',None),('POST',f'/rest/v1/{t}',row),('PATCH',f'/rest/v1/{t}?{where}',change),('DELETE',f'/rest/v1/{t}?{where}',None)):
     out[f'{who} {method} {t}']=raw(method,path,body,token)[0]
  expect(all(c in (401,403) for c in out.values()),{k:v for k,v in out.items() if v not in (401,403)})
  if LOCAL:
   after=db('select (select count(*) from public.bandstand_consent),(select count(*) from public.bandstand_erp_recordings),(select count(*) from public.bandstand_model_releases)')
   expect(before==after,(before,after))
  return f'{len(out)} well-formed probes refused with {sorted(set(out.values()))}'+('; row counts unchanged' if LOCAL else '')
 @check('A04','access','A tampered access token is rejected by Auth and the database API')
 def _():
  t=state['a']['token'];bad=secret(t[:-3]+('AAA' if not t.endswith('AAA') else 'BBB'))
  codes=(raw('GET','/auth/v1/user',token=bad)[0],raw('POST','/rest/v1/rpc/bandstand_sharing_status',{},bad)[0])
  expect(all(c in (401,403) for c in codes),codes);return f'Auth {codes[0]}, REST {codes[1]}'
 @check('A05','access','An expired but correctly signed access token is rejected (control: same token unexpired is accepted)',local_only=True)
 def _():
  status=json.loads(subprocess.run(['supabase','status','-o','json'],cwd=ROOT,capture_output=True,text=True,timeout=60).stdout)
  key=status['JWT_SECRET'];secret(key)
  live=mint(state['a']['user_id'],time.time()+600,key);dead=mint(state['a']['user_id'],time.time()-60,key)
  control=raw('POST','/rest/v1/rpc/bandstand_sharing_status',{},live)[0]
  expect(control==200,f'control token not accepted ({control}); signing scheme differs, test inconclusive')
  codes=(raw('POST','/rest/v1/rpc/bandstand_sharing_status',{},dead)[0],raw('GET','/auth/v1/user',token=dead)[0])
  expect(all(c in (401,403) for c in codes),codes);return f'control 200; expired: REST {codes[0]}, Auth {codes[1]}'

 # Two people: A must not see, alter or delete B's records, and the reverse.
 @check('I01','isolation','Second synthetic account B is created and confirmed')
 def _():
  state['b']=raw_account(email['b'],pw['b'],mail);return 'confirmed through emailed code'
 @check('I02','isolation','A and B each consent and upload one synthetic ERP record')
 def _():
  for who,marker,rid in (('a',11,'00000000-0000-4000-8000-00000000000a'),('b',22,'00000000-0000-4000-8000-00000000000b')):
   token=state['a']['token'] if who=='a' else state['b']['access']
   for fn,body in (('bandstand_set_erp_consent',{'allow_sharing':True}),('bandstand_upload_erp',{'recording_id':rid,'recording':synthetic_erp(marker)})):
    c,b=raw('POST','/rest/v1/rpc/'+fn,body,token);expect(c in (200,204),f'{who} {fn} {c} {b}')
  return 'two consents and two records stored'
 def listed(token):
  c,b=raw('POST','/rest/v1/rpc/bandstand_list_erp',{},token);expect(c==200,c);return {r['recording_id'] for r in b}
 @check('I03','isolation','Each person lists only their own records')
 def _():
  a,b=listed(state['a']['token']),listed(state['b']['access'])
  expect(a=={'00000000-0000-4000-8000-00000000000a'} and b=={'00000000-0000-4000-8000-00000000000b'},(a,b));return 'A sees only A; B sees only B'
 @check('I04','isolation','RPCs ignore attempts to name another user')
 def _():
  out={fn:raw('POST','/rest/v1/rpc/'+fn,{'user_id':state['a']['user_id']},state['b']['access'])[0] for fn in ('bandstand_list_erp','bandstand_delete_erp','bandstand_sharing_status')}
  expect(all(c>=400 for c in out.values()),out)
  expect(listed(state['a']['token'])=={'00000000-0000-4000-8000-00000000000a'},'A records changed');return 'extra user_id argument rejected: '+json.dumps(out)
 @check('I05','isolation','B withdrawing consent and deleting records leaves A untouched')
 def _():
  for fn,body in (('bandstand_set_erp_consent',{'allow_sharing':False}),('bandstand_delete_erp',{})):
   c,_=raw('POST','/rest/v1/rpc/'+fn,body,state['b']['access']);expect(c in (200,204),c)
  expect(listed(state['b']['access'])==set(),'B still has records')
  expect(listed(state['a']['token'])=={'00000000-0000-4000-8000-00000000000a'},'A record lost')
  c,s=raw('POST','/rest/v1/rpc/bandstand_sharing_status',{},state['a']['token']);expect(s['erp_sharing'] is True,s);return 'A consent and record intact'
 @check('I06','isolation','B cannot upload without consent after withdrawing')
 def _():
  c,_=raw('POST','/rest/v1/rpc/bandstand_upload_erp',{'recording_id':'00000000-0000-4000-8000-0000000000bb','recording':synthetic_erp(33)},state['b']['access']);expect(c>=400,c);return f'HTTP {c}'
 @check('I07','isolation','B deleting their own account removes only B',local_only=False)
 def _():
  c,_=raw('POST','/rest/v1/rpc/bandstand_delete_own_account',{},state['b']['access']);expect(c in (200,204),c)
  expect(listed(state['a']['token'])=={'00000000-0000-4000-8000-00000000000a'},'A record lost')
  if LOCAL:
   n=db(f"select (select count(*) from auth.users where id={quote(state['b']['id'])})+(select count(*) from public.bandstand_consent where user_id={quote(state['b']['id'])})+(select count(*) from public.bandstand_erp_recordings where user_id={quote(state['b']['id'])})")
   expect(n=='0',f'{n} B rows remain');return 'B user, consent and record rows: 0; A intact'
  return 'A intact (row counts need the SQL editor on a cloud project)'

 # Password recovery and the reach of revocation.
 @check('R01','recovery','Recovery request returns the same message for real and unknown addresses')
 def _():
  state['device2']=password_grant(email['a'],pw['a'])
  r=app('recover',{'email':email['a']})
  u=app('recover',{'email':f'nobody-{run}@example.test'});expect(r['message']==u['message'],(r,u));return r['message']
 # Must run within the 5 s resend interval of R01 and before its code is read; a successful
 # second request would replace that code.
 @check('R03','recovery','A second request inside the resend interval is rate limited with a clear message')
 def _():
  e=app_error('recover',{'email':email['a']});expect(getattr(e,'status',0)==429,(getattr(e,'status',0),str(e)));return str(e)
 @check('R02','recovery','Recovery email arrives with a code and in-app instructions')
 def _():
  m=mail.code(email['a'],'recovery');state['rcode']=m['code']
  if args.mail=='mailpit':expect('Choose a new password' in m['body'] and 'Bandstand' in m['subject'],m['subject'])
  return f"subject: {m['subject']}"
 @check('R04','recovery','A recovery code cannot reset a different email address')
 def _():
  e=app_error('reset',{'email':email['c'],'code':state['rcode'],'password':pw['a2']});password_grant(email['a'],pw['a'])
  return f'{e}; original password still works'
 @check('R05','recovery','Malformed proofs are rejected before contacting the server')
 def _():
  for code in ('12',B['url']+'/auth/v1/verify?token=x&type=signup','https://evil.example/auth/v1/verify?token=x&type=recovery'):app_error('reset',{'email':email['a'],'code':code,'password':pw['a2']})
  return 'three malformed proofs refused'
 @check('R06','recovery','Reset with the emailed code sets the new password and ends the app session')
 def _():
  r=app('reset',{'email':email['a'],'code':state['rcode'],'password':pw['a2']});expect(r['signed_in'] is False and accounts._session is None,r)
  expect(session_vault.load() is None,'Keychain still holds a session');return r['message']
 @check('R07','recovery','The old password stops working and the new one works')
 def _():
  c=raw('POST','/auth/v1/token?grant_type=password',{'email':email['a'],'password':pw['a']})[0];expect(c==400,c)
  state['a3']=password_grant(email['a'],pw['a2']);return f'old password HTTP {c}; new password accepted'
 @check('R08','recovery','A used recovery code cannot be reused')
 def _():
  app_error('reset',{'email':email['a'],'code':state['rcode'],'password':pw['a']});return 'refused'
 @check('R09','recovery','Reach of the reset: other devices\' sessions (documents actual scope)')
 def _():
  d=state['device2'];r=refresh_status(d['refresh']);u=raw('GET','/auth/v1/user',token=d['access'])[0];p=raw('POST','/rest/v1/rpc/bandstand_sharing_status',{},d['access'])[0]
  state['reset_scope']={'refresh':r,'auth_user':u,'rest':p}
  expect(r!=200,'other device can still refresh after a password reset')
  return f'other device refresh token HTTP {r}; its unexpired access token: Auth /user HTTP {u}, database RPC HTTP {p}'

 # Sign-out scope.
 @check('O01','signout','Sign-out clears the app session and Keychain; reach to other devices documented')
 def _():
  app('signin',{'email':email['a'],'password':pw['a2'],'remember':True});other=password_grant(email['a'],pw['a2'])
  r=app('signout');expect(r['signed_in'] is False and accounts._session is None and session_vault.load() is None,r)
  s=reopen_status();expect(not s['signed_in'],s)
  c=refresh_status(other['refresh']);state['signout_scope']=c
  return f'local session and Keychain cleared; reopened app signed out; another device\'s refresh token afterwards: HTTP {c} ({"revoked: sign-out is global" if c!=200 else "still valid: sign-out is local"})'

 # Expired codes, resend, and mail-server failure (local stack).
 @check('E01','signup','An expired confirmation code is rejected (send time backdated two hours in the local database)',local_only=True)
 def _():
  app('signup',{'email':email['c'],'password':pw['c'],'policy_version':POLICY_VERSION,'acknowledged':True});code=mail.code(email['c'],'confirmation')['code']
  db(f"update auth.users set confirmation_sent_at=now()-interval '2 hours' where lower(email)=lower({quote(email['c'])})")
  e=app_error('confirm',{'email':email['c'],'code':code});expect(str(e)==accounts.AUTH_MESSAGES['otp_expired'],str(e));return f'{getattr(e,"status","")} {e}'
 @check('E02','signup','Signing up again sends a fresh code that confirms the account (as the email instructions say)',local_only=True)
 def _():
  time.sleep(6);r=app('signup',{'email':email['c'],'password':pw['c'],'policy_version':POLICY_VERSION,'acknowledged':True})
  code=mail.code(email['c'],'confirmation')['code'];c=app('confirm',{'email':email['c'],'code':code});expect('Email confirmed' in c['message'],c);return c['message']
 @check('E03','email','Mail-server failure produces an actionable error and no false success',local_only=True)
 def _():
  container=f'supabase_inbucket_{PROJECT}'
  subprocess.run([DOCKER,'stop',container],capture_output=True,check=True,timeout=60)
  try:e=app_error('signup',{'email':email['d'],'password':pw['d'],'policy_version':POLICY_VERSION,'acknowledged':True})
  finally:subprocess.run([DOCKER,'start',container],capture_output=True,check=True,timeout=60)
  expect('No email delivery is confirmed' in str(e),str(e));return str(e)
 @check('E04','email','A failed confirmation send leaves no account behind, so Resend has nothing to send (documents behavior)',local_only=True)
 def _():
  n=db(f"select count(*) from auth.users where lower(email)=lower({quote(email['d'])})");expect(n=='0',f'{n} rows')
  return 'observed',"Auth rolled the signup back when the email could not be sent: 0 user rows. The person must sign up again once email works; Resend answers OK but sends nothing."
 @check('E05','email','Resend delivers a fresh code for an unconfirmed account whose first email was lost, and the code confirms it',local_only=True)
 def _():
  app('signup',{'email':email['e'],'password':pw['e'],'policy_version':POLICY_VERSION,'acknowledged':True});mail.code(email['e'],'confirmation')  # first code "lost": read and discarded
  time.sleep(6);r=app('resend',{'email':email['e']});expect(r['message'].startswith('If this address has an unconfirmed account'),r)
  u=app('resend',{'email':f'nobody-{run}@example.test'});expect(u['message']==r['message'],'resend answer differs for an unknown address')
  code=mail.code(email['e'],'confirmation')['code'];c=app('confirm',{'email':email['e'],'code':code});expect('Email confirmed' in c['message'],c)
  return 'same answer for an unknown address; the resent code confirmed the account'

 # Network faults.
 @check('N01','network','Unreachable account server: clear message, local recording unaffected')
 def _():
  url=accounts.URL;accounts.URL='http://127.0.0.1:9'
  try:e=app_error('signin',{'email':email['a'],'password':pw['a2']})
  finally:accounts.URL=url
  expect('Local recording remains available' in str(e),str(e));return str(e)
 @check('N02','network','A server that accepts but never answers times out with the same clear message')
 def _():
  server=socket.socket();server.bind(('127.0.0.1',0));server.listen(1);held=[]
  threading.Thread(target=lambda:held.append(server.accept()),daemon=True).start()
  url=accounts.URL;accounts.URL=f'http://127.0.0.1:{server.getsockname()[1]}';start=time.time()
  try:e=app_error('signin',{'email':email['a'],'password':pw['a2']})
  finally:accounts.URL=url;server.close()
  expect('Local recording remains available' in str(e),str(e));return f'{e} (after {time.time()-start:.0f}s)'

 # Deletion of the designated test account A.
 @check('D01','deletion','Deleting designated account A removes the cloud account and clears the local session')
 def _():
  app('signin',{'email':email['a'],'password':pw['a2'],'remember':True});state['a_last']=dict(accounts._session);secret(state['a_last']['token']);secret(state['a_last']['refresh_token'])
  local=DATA_ROOT/'synthetic-local-recording.txt';local.write_text('synthetic local file');state['local']=local
  r=app('delete',{'confirmation':'DELETE'});expect(r['signed_in'] is False and accounts._session is None and session_vault.load() is None,r);return r['message']
 @check('D02','deletion','A\'s auth user, consent row and shared ERP rows are gone',local_only=True)
 def _():
  uid=quote(state['a_last']['user_id'])
  n=db(f'select (select count(*) from auth.users where id={uid}),(select count(*) from public.bandstand_consent where user_id={uid}),(select count(*) from public.bandstand_erp_recordings where user_id={uid})')
  expect(n=='0|0|0',n);return 'auth.users 0, bandstand_consent 0, bandstand_erp_recordings 0'
 @check('D03','deletion','After deletion the old credentials no longer work (documents token behavior)')
 def _():
  t=state['a_last'];sign=raw('POST','/auth/v1/token?grant_type=password',{'email':email['a'],'password':pw['a2']})[0];ref=refresh_status(t['refresh_token']);user=raw('GET','/auth/v1/user',token=t['token'])[0]
  rest_status,rest=raw('POST','/rest/v1/rpc/bandstand_list_erp',{},t['token']);up=raw('POST','/rest/v1/rpc/bandstand_set_erp_consent',{'allow_sharing':True},t['token'])[0]
  state['deleted_token']={'rest_list':rest_status,'rest_list_rows':len(rest or []) if isinstance(rest,list) else None,'set_consent':up}
  expect(sign==400 and ref!=200 and user in (401,403,404),(sign,ref,user))
  expect(not (isinstance(rest,list) and rest),'deleted user still lists records')
  return f'password sign-in HTTP {sign}; refresh HTTP {ref}; Auth /user HTTP {user}; unexpired access token on RPCs: list HTTP {rest_status} ({state["deleted_token"]["rest_list_rows"]} rows), set-consent HTTP {up}'
 @check('D04','deletion','Local files are untouched by cloud account deletion, as the app message says')
 def _():
  expect(state['local'].exists(),'local file removed');state['local'].unlink();return 'synthetic local file still present after deletion'

 @check('H01','hygiene','No user-visible message or result contains a password, token or email code')
 def _():
  leaks=[m for m in MESSAGES if any(s in m for s in SECRETS)];expect(not leaks,f'{len(leaks)} messages leaked a secret');return f'{len(MESSAGES)} messages scanned'

 try:session_vault.clear()
 except ValueError:pass
 out=ROOT/'build/acceptance';out.mkdir(parents=True,exist_ok=True)
 report={'run':run,'backend':{'name':B['name'],'url':B['url']},'mail':args.mail,'observations':{k:state.get(k) for k in ('reset_scope','signout_scope','deleted_token')},'results':RESULTS}
 (out/f'accounts-{run}.json').write_text(redact(json.dumps(report,indent=2)))
 rows=['| ID | Area | Check | Outcome | Level | Evidence |','|---|---|---|---|---|---|']+[f"| {r['id']} | {r['area']} | {r['check']} | {r['outcome']} | {r['level']} | {r['evidence'].replace('|','/')} |" for r in RESULTS]
 (out/f'accounts-{run}.md').write_text(redact(f"# Account acceptance run {run}\n\nBackend: {B['name']} ({B['url']}), mail: {args.mail}\n\n"+'\n'.join(rows)+'\n'))
 counts={o:sum(r['outcome']==o for r in RESULTS) for o in ('pass','fail','not run')}
 print(json.dumps(counts),'->',out/f'accounts-{run}.md')
 sys.exit(1 if counts['fail'] else 0)

if __name__=='__main__':main()
