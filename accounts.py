"""Supabase identity only: explicit field allowlists; tokens stay in process memory."""
import json, os, time, threading, urllib.request, urllib.error, urllib.parse
URL='https://ovoxgrqhdvzcjqjzgnqk.supabase.co'
PUBLISHABLE_KEY='sb_publishable_YxUASj1-IWhc9YAo_Qf-hw_NxlqkiJf'
_lock=threading.RLock()
_session=None
_restore_attempted=False
_restore_retry_at=0
_session_notice=''
ERP_SHARING_AVAILABLE=True
class AccountError(ValueError):
 def __init__(self,message,status=0):super().__init__(message);self.status=status

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def _request(path,body=None,token=None,method=None):
 if path not in ('/auth/v1/token?grant_type=refresh_token','/rest/v1/rpc/bandstand_sharing_status','/rest/v1/rpc/bandstand_list_erp','/rest/v1/rpc/bandstand_set_erp_consent','/rest/v1/rpc/bandstand_upload_erp','/rest/v1/rpc/bandstand_delete_erp','/auth/v1/signup','/auth/v1/recover','/auth/v1/verify','/auth/v1/token?grant_type=password','/auth/v1/logout','/auth/v1/user','/rest/v1/rpc/bandstand_delete_own_account'):
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
  _session={'token':result['access_token'],'refresh_token':result.get('refresh_token',refresh),'email':user['email'],'user_id':user['id'],'expires_at':time.time()+result.get('expires_in',3600),'remembered':remembered,'preferences':user.get('user_metadata',{}).get('bandstand_preferences',{})}
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
 return {'signed_in':_session is not None,'email':_session['email'] if _session else None,'remembered':bool(_session and _session.get('remembered')),'message':_session_notice if not _session else '', 'preferences':_session.get('preferences',{}) if _session else {}}

def account(action,body=None):
 global _session,_restore_attempted,_session_notice
 body=body or {}
 with _lock:
  if action=='status':
   try:_restore()
   except ValueError:pass
  if action=='status':return _status()
  if action in ('erp-consent','erp-upload','erp-delete','erp-status','erp-list'):
   if not ERP_SHARING_AVAILABLE:raise ValueError('ERP sharing is awaiting database activation. No recording has been uploaded.')
   _restore()
   if not _session:raise ValueError('Sign in to manage shared ERP recordings.')
   if action=='erp-status':return _request('/rest/v1/rpc/bandstand_sharing_status',{},_session['token'])
   if action=='erp-list':return _request('/rest/v1/rpc/bandstand_list_erp',{},_session['token'])
   if action=='erp-consent':
    if body.get('sharing_policy')!='erp-sharing-v1' or type(body.get('allow')) is not bool:raise ValueError('Review ERP sharing terms and choose Yes or No.')
    _request('/rest/v1/rpc/bandstand_set_erp_consent',{'allow_sharing':body['allow']},_session['token'])
    return {'saved':True}
   if action=='erp-delete':
    if body.get('confirmation')!='DELETE':raise ValueError('Type DELETE to delete shared recordings.')
    _request('/rest/v1/rpc/bandstand_delete_erp',{},_session['token']);return {'message':'Shared ERP recordings deleted. Local copies remain.'}
   from erp_sharing import payload
   ident,recording=payload(str(body.get('recording_id','')))
   _request('/rest/v1/rpc/bandstand_upload_erp',{'recording_id':ident,'recording':recording},_session['token'])
   return {'message':'ERP trial waveforms shared successfully.'}
  if action=='preferences':
   _restore()
   if not _session:raise ValueError('Sign in to save choices to your account.')
   from enrollment import POLICY_VERSION
   if body.get('policy_version')!=POLICY_VERSION or body.get('acknowledged') is not True:
    raise ValueError('Read and acknowledge the current privacy notice.')
   # Preferences only, not trusted upload authorization. No text or EEG accepted.
   preferences={'policy_version':POLICY_VERSION,'acknowledged':True,
                'erp_sharing_requested':body.get('erp_sharing_requested') is True,
                'decoder_interest_requested':body.get('decoder_interest_requested') is True,'sharing_choices_reviewed':True,'erp_policy':body.get('erp_policy') if body.get('erp_policy')=='erp-sharing-v1' else None}
   _request('/auth/v1/user',{'data':{'bandstand_preferences':preferences}},_session['token'],method='PUT')
   _session['preferences']=preferences
   return {'saved':True,'message':'Data sharing settings saved.'}
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
  result=_request('/auth/v1/signup' if action=='signup' else '/auth/v1/token?grant_type=password',credentials)
  if result.get('access_token'):
   user=_request('/auth/v1/user',token=result['access_token'])
   _session={'token':result['access_token'],'email':user['email'],'user_id':user['id'],'expires_at':time.time()+result.get('expires_in',3600),'refresh_token':result.get('refresh_token'),'remembered':body.get('remember') is True,'preferences':user.get('user_metadata',{}).get('bandstand_preferences',{})}
   if body.get('remember') is True:
    try:_persist(result)
    except ValueError:_session['remembered']=False;_session_notice='Signed in for this session only. Keychain storage was unavailable.'
   return {**_status(),'message':_session_notice}
  return {'signed_in':False,'message':'Check your email to confirm your account, then sign in.'}
