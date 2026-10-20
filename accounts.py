"""Supabase identity only: explicit field allowlists; tokens stay in process memory."""
import json, os, time, threading, urllib.request, urllib.error, urllib.parse
import backend_config
BACKEND=backend_config.load()
URL=BACKEND['url']
PUBLISHABLE_KEY=BACKEND['publishable_key']
_lock=threading.RLock()
_session=None
_restore_attempted=False
_restore_retry_at=0
_session_notice=''
ERP_SHARING_AVAILABLE=True
class AccountError(ValueError):
 def __init__(self,message,status=0):super().__init__(message);self.status=status

# Fixed wording for Supabase Auth error codes. Remote messages are never shown. Auth already reveals an
# existing account to any direct caller (user_already_exists), so saying so here exposes nothing new.
AUTH_MESSAGES={'invalid_credentials':'Email or password is incorrect.',
 'email_not_confirmed':'Confirm your email with the code we sent before signing in.',
 'user_already_exists':'This email already has an account. Sign in, or use Forgot password? to reset it.',
 'email_exists':'This email already has an account. Sign in, or use Forgot password? to reset it.',
 'weak_password':'Choose a stronger password.',
 'same_password':'Choose a password different from your current one.',
 'otp_expired':'This code is wrong, expired or already used. Request a new email.',
 'email_address_invalid':'Enter a valid email address.',
 'email_address_not_authorized':'The account server cannot email this address yet. Its participant email delivery is not configured.',
 'signup_disabled':'New accounts are not being accepted right now.'}

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def _request(path,body=None,token=None,method=None):
 if path not in ('/auth/v1/token?grant_type=refresh_token','/rest/v1/rpc/bandstand_sharing_status','/rest/v1/rpc/bandstand_list_erp','/rest/v1/rpc/bandstand_set_erp_consent','/rest/v1/rpc/bandstand_upload_erp','/rest/v1/rpc/bandstand_delete_erp','/auth/v1/signup','/auth/v1/resend','/auth/v1/recover','/auth/v1/verify','/auth/v1/token?grant_type=password','/auth/v1/logout','/auth/v1/user','/rest/v1/rpc/bandstand_delete_own_account'):
  raise ValueError('Account endpoint not allowed')
 if method is not None and (path!='/auth/v1/user' or method!='PUT'):
  raise ValueError('Account method not allowed')
 headers={'apikey':PUBLISHABLE_KEY,'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 req=urllib.request.Request(URL+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
 try:
  with urllib.request.build_opener(NoRedirect).open(req,timeout=15) as r:
   raw=r.read();return json.loads(raw) if raw else {}
 except urllib.error.HTTPError as e:
  # Never echo remote payloads, passwords or tokens into logs/UI.
  if e.code==429:raise AccountError('Too many attempts. Please wait before trying again.',429) from None
  if e.code>=500:raise ValueError('The account server failed to complete this request. For signup or recovery, the administrator should check the email delivery configuration. No email delivery is confirmed.') from None
  # Only the machine-readable error code is read, and only allowlisted codes change the wording.
  try:code=json.loads(e.read(65536)).get('error_code')
  except (OSError,ValueError,AttributeError):code=None
  if code in AUTH_MESSAGES:raise AccountError(AUTH_MESSAGES[code],e.code) from None
  raise AccountError('Account request failed. Check your details and email confirmation.',e.code) from None
 except (OSError,ValueError):raise ValueError('Account service unavailable. Local recording remains available.') from None

def _email_proof(email,code,kind):
 if '@' not in email or len(email)>254:raise ValueError('Enter your account email address.')
 if code.isascii() and code.isdigit() and 6<=len(code)<=10:
  return {'email':email,'token':code,'type':'recovery' if kind=='recovery' else 'email'}
 link=urllib.parse.urlsplit(code);query=urllib.parse.parse_qs(link.query)
 if link.scheme!='https' or link.netloc!=urllib.parse.urlsplit(URL).netloc or link.path!='/auth/v1/verify' or query.get('type')!=[kind] or len(query.get('token',[]))!=1 or link.fragment:
  raise ValueError('Paste the email code or copy the unopened link from your email.')
 return {'token_hash':query['token'][0],'type':kind}

def _persist(result):
 import session_vault
 if result.get('refresh_token'):session_vault.save(result['refresh_token'])

def _forget():
 import session_vault
 session_vault.clear()

def _restore():
 global _session,_restore_attempted,_restore_retry_at,_session_notice
 if _session and time.time()<_session.get('expires_at',float('inf'))-60:return
 if not _session and (_restore_attempted or time.time()<_restore_retry_at):return
 import session_vault
 try:
  refresh=_session.get('refresh_token') if _session else session_vault.load()
  if not refresh:
   _session=None;_restore_attempted=True;return
  remembered=_session.get('remembered',False) if _session else True
  result=_request('/auth/v1/token?grant_type=refresh_token',{'refresh_token':refresh})
  user=_request('/auth/v1/user',token=result['access_token'])
  _session={'token':result['access_token'],'refresh_token':result.get('refresh_token',refresh),'email':user['email'],'user_id':user['id'],'expires_at':time.time()+result.get('expires_in',3600),'remembered':remembered,'display_name':user.get('user_metadata',{}).get('display_name',''),'preferences':user.get('user_metadata',{}).get('bandstand_preferences',{})}
  if remembered:_persist(result)
  _session_notice='';_restore_attempted=True
 except AccountError as e:
  _session=None
  if e.status in (400,401,403):
   _forget();_restore_attempted=True;_session_notice='Your saved session expired. Please sign in again.'
  else:_restore_retry_at=time.time()+30
  raise
 except (ValueError,OSError):
  _session=None;_restore_retry_at=time.time()+30
  _session_notice='Saved sign-in is temporarily unavailable. Local recording still works.'
  raise ValueError(_session_notice) from None

def _status():
 return {'display_name':_session.get('display_name','') if _session else '', 'signed_in':_session is not None,'email':_session['email'] if _session else None,'remembered':bool(_session and _session.get('remembered')),'message':_session_notice if not _session else '', 'preferences':_session.get('preferences',{}) if _session else {},'backend':BACKEND['name']}

_wake=threading.Event();_worker=None

def _outbox_pass(now=None):
 """Upload due outbox items for the signed-in account. Tokens are captured with the account they belong to,
 and every step re-checks that the same account is still signed in."""
 import erp_outbox
 from erp_sharing import payload
 with _lock:
  try:_restore()
  except ValueError:return 0
  if not _session or not ERP_SHARING_AVAILABLE:return 0
  user,token=_session['user_id'],_session['token']
 def same_account():
  with _lock:return bool(_session) and _session['user_id']==user
 def consent():
  if not same_account():raise erp_outbox.TransientError()
  try:return _request('/rest/v1/rpc/bandstand_sharing_status',{},token).get('erp_sharing') is True
  except ValueError:raise erp_outbox.TransientError() from None
 def upload(item):
  if not same_account():raise erp_outbox.TransientError()
  ident,recording=payload(item['session'])
  if ident!=item['id']:raise ValueError('The local recording no longer matches the queued item.')
  try:_request('/rest/v1/rpc/bandstand_upload_erp',{'recording_id':ident,'recording':recording},token)
  except AccountError as e:
   if e.status in (401,408,429):raise erp_outbox.TransientError() from None
   raise ValueError('The server refused this recording.') from None
  except ValueError:raise erp_outbox.TransientError() from None
 return erp_outbox.process(user,consent,upload,now)

def start_outbox(interval=20):
 """Start the background uploader once per process (desktop service and preview server)."""
 global _worker
 if _worker and _worker.is_alive():return
 import erp_outbox;erp_outbox.recover()
 def loop():
  while True:
   try:_outbox_pass()
   except Exception:pass  # sharing must never interfere with local recording
   _wake.wait(interval);_wake.clear()
 _worker=threading.Thread(target=loop,name='erp-outbox',daemon=True);_worker.start()

def account(action,body=None):
 global _session,_restore_attempted,_session_notice
 body=body or {}
 with _lock:
  if action=='status':
   try:_restore()
   except ValueError:pass
  if action=='status':return _status()
  if action in ('erp-consent','erp-upload','erp-delete','erp-status','erp-list','erp-enqueue','erp-outbox','erp-retry'):
   if not ERP_SHARING_AVAILABLE:raise ValueError('ERP sharing is awaiting database activation. No recording has been uploaded.')
   _restore()
   if not _session:raise ValueError('Sign in to manage shared ERP recordings.')
   if action=='erp-status':return _request('/rest/v1/rpc/bandstand_sharing_status',{},_session['token'])
   if action=='erp-list':return _request('/rest/v1/rpc/bandstand_list_erp',{},_session['token'])
   import erp_outbox
   if action=='erp-consent':
    if body.get('sharing_policy')!='erp-sharing-v1' or type(body.get('allow')) is not bool:raise ValueError('Review ERP sharing terms and choose Yes or No.')
    # Withdrawal stops queued uploads locally first, so it holds even if the server cannot be reached.
    if not body['allow']:erp_outbox.withdraw(_session.get('user_id'))
    _request('/rest/v1/rpc/bandstand_set_erp_consent',{'allow_sharing':body['allow']},_session['token'])
    return {'saved':True}
   if action=='erp-enqueue':
    # Queue only the recording that just finished; nothing earlier is backfilled. The server's consent is
    # checked again immediately before every upload attempt.
    prefs=_session.get('preferences',{})
    if not (prefs.get('erp_auto_share') is True and prefs.get('erp_sharing_requested') is True):return {'queued':False}
    from erp_sharing import payload
    recording=str(body.get('recording_id',''));ident,_=payload(recording)
    erp_outbox.enqueue(ident,recording,_session['user_id'],'erp-sharing-v1');_wake.set()
    return {'queued':True,**erp_outbox.summary(_session['user_id'])}
   if action=='erp-outbox':return erp_outbox.summary(_session['user_id'])
   if action=='erp-retry':
    erp_outbox.retry(_session['user_id']);_wake.set();return erp_outbox.summary(_session['user_id'])
   if action=='erp-delete':
    if body.get('confirmation')!='DELETE':raise ValueError('Type DELETE to delete shared recordings.')
    _request('/rest/v1/rpc/bandstand_delete_erp',{},_session['token']);return {'message':'Shared ERP recordings deleted. Local copies remain.'}
   from erp_sharing import payload
   ident,recording=payload(str(body.get('recording_id','')))
   _request('/rest/v1/rpc/bandstand_upload_erp',{'recording_id':ident,'recording':recording},_session['token'])
   return {'message':'ERP trial waveforms shared successfully.'}
  if action=='profile':
   _restore()
   if not _session:raise ValueError('Sign in to edit your display name.')
   name=str(body.get('display_name','')).strip()
   if not 1<=len(name)<=40 or any(ord(c)<32 for c in name):raise ValueError('Enter a display name of 1–40 characters.')
   _request('/auth/v1/user',{'data':{'display_name':name}},_session['token'],method='PUT')
   _session['display_name']=name
   return _status()
  if action=='preferences':
   _restore()
   if not _session:raise ValueError('Sign in to save choices to your account.')
   from enrollment import POLICY_VERSION
   if body.get('policy_version')!=POLICY_VERSION or body.get('acknowledged') is not True:
    raise ValueError('Read and acknowledge the current privacy notice.')
   # Preferences only, not trusted upload authorization. No text or EEG accepted.
   from sharing_policy import choices
   preferences=choices(body)
   _request('/auth/v1/user',{'data':{'bandstand_preferences':preferences}},_session['token'],method='PUT')
   _session['preferences']=preferences
   return {'saved':True,'message':'Data sharing settings saved.'}
  if action=='resend':
   # Only the address is sent. The answer is the same whether or not the address has an unconfirmed account.
   email=str(body.get('email','')).strip()
   if '@' not in email or len(email)>254:raise ValueError('Enter your account email address.')
   _request('/auth/v1/resend',{'type':'signup','email':email})
   return {'message':'If this address has an unconfirmed account, a new code will arrive within a few minutes. Check spam, junk and Promotions too.'}
  if action=='recover':
   email=str(body.get('email','')).strip()
   if '@' not in email or len(email)>254:raise ValueError('Enter your account email address.')
   _request('/auth/v1/recover',{'email':email})
   return {'message':'If this address has an account, a password reset email will arrive shortly. Check spam too.'}
  if action=='confirm':
   email=str(body.get('email','')).strip();code=str(body.get('code','')).strip()
   result=_request('/auth/v1/verify',_email_proof(email,code,'signup'))
   token=result.get('access_token')
   if not token:raise ValueError('Email verification failed. Check the code or request a new account email.')
   try:
    user=_request('/auth/v1/user',token=token)
    if user.get('email','').casefold()!=email.casefold():raise ValueError('This confirmation belongs to a different email address.')
   finally:
    try:_request('/auth/v1/logout',{},token)
    except ValueError:pass
   return {'message':'Email confirmed. You can now sign in.'}
  if action=='reset':
   # Recovery happens here, never on a public GitHub Pages password form.
   email=str(body.get('email','')).strip();code=str(body.get('code','')).strip()
   password=body.get('password','')
   if '@' not in email or len(email)>254 or not isinstance(password,str) or not 8<=len(password)<=1024:
    raise ValueError('Enter your account email and a new password of at least eight characters.')
   proof=_email_proof(email,code,'recovery')
   result=_request('/auth/v1/verify',proof)
   token=result.get('access_token')
   if not token:raise ValueError('Recovery verification failed. Request a new email.')
   try:
    user=_request('/auth/v1/user',token=token)
    if user.get('email','').casefold()!=email.casefold():raise ValueError('This recovery link belongs to a different email address.')
    _request('/auth/v1/user',{'password':password},token,method='PUT')
   finally:
    try:_request('/auth/v1/logout',{},token)
    except ValueError:pass
   _forget();_session=None
   return {'signed_in':False,'message':'Password updated. Sign in with your new password.'}
  if action=='delete':
   _restore()
   if not _session:raise ValueError('Sign in before deleting your account.')
   if body.get('confirmation')!='DELETE':raise ValueError('Type DELETE to confirm account deletion.')
   _request('/rest/v1/rpc/bandstand_delete_own_account',{},_session['token'])
   import erp_outbox;erp_outbox.forget(_session.get('user_id'))
   _forget();_session=None
   return {'signed_in':False,'message':'Account and consent record deleted. Local recordings remain on this computer.'}
  if action=='signout':
   previous=_session;_session=None;_restore_attempted=True;_session_notice=''
   try:_forget()
   except ValueError:raise ValueError('Signed out of this session, but Keychain could not be cleared. Retry sign out before leaving this computer.') from None
   if previous:
    try:_request('/auth/v1/logout',{},previous['token'])
    except ValueError:pass
   return {'signed_in':False}
  if action not in ('signin','signup'):raise ValueError('Unknown account action')
  email=str(body.get('email','')).strip();password=body.get('password','')
  if '@' not in email or len(email)>254 or not isinstance(password,str) or not 8<=len(password)<=1024:
   raise ValueError('Enter your email and a password of at least eight characters.')
  if action=='signup':
   from enrollment import POLICY_VERSION
   if body.get('policy_version')!=POLICY_VERSION or body.get('acknowledged') is not True:
    raise ValueError('Read and acknowledge the current privacy notice before creating an account.')
  _forget();_restore_attempted=True;_session_notice=''
  _session=None
  credentials={'email':email,'password':password}
  if action=='signup':credentials['data']={'bandstand_privacy':{'policy_version':body['policy_version'],'acknowledged':True}}
  if action=='signup' and body.get('display_name'):
   name=str(body['display_name']).strip()
   if not 1<=len(name)<=40 or any(ord(c)<32 for c in name):raise ValueError('Enter a display name of 1–40 characters.')
   credentials['data']['display_name']=name
  result=_request('/auth/v1/signup' if action=='signup' else '/auth/v1/token?grant_type=password',credentials)
  if result.get('access_token'):
   user=_request('/auth/v1/user',token=result['access_token'])
   _session={'token':result['access_token'],'email':user['email'],'user_id':user['id'],'expires_at':time.time()+result.get('expires_in',3600),'refresh_token':result.get('refresh_token'),'remembered':body.get('remember') is True,'display_name':user.get('user_metadata',{}).get('display_name',''),'preferences':user.get('user_metadata',{}).get('bandstand_preferences',{})}
   if body.get('remember') is True:
    try:_persist(result)
    except ValueError:_session['remembered']=False;_session_notice='Signed in for this session only. Keychain storage was unavailable.'
   return {**_status(),'message':_session_notice}
  return {'signed_in':False,'message':'Check your email to confirm your account, then sign in.'}
