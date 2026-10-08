"""Supabase identity only: explicit field allowlists; tokens stay in process memory."""
import json, os, threading, urllib.request, urllib.error, urllib.parse
URL='https://ovoxgrqhdvzcjqjzgnqk.supabase.co'
PUBLISHABLE_KEY='sb_publishable_YxUASj1-IWhc9YAo_Qf-hw_NxlqkiJf'
_lock=threading.RLock()
_session=None
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def _request(path,body=None,token=None,method=None):
 if path not in ('/auth/v1/signup','/auth/v1/recover','/auth/v1/verify','/auth/v1/token?grant_type=password','/auth/v1/logout','/auth/v1/user','/rest/v1/rpc/bandstand_delete_own_account'):
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
  if e.code==429:raise ValueError('Too many attempts. Please wait before trying again.') from None
  raise ValueError('Account request failed. Check your details and email confirmation.') from None
 except (OSError,ValueError):raise ValueError('Account service unavailable. Local recording remains available.') from None

def account(action,body=None):
 global _session
 body=body or {}
 with _lock:
  if action=='status':return {'signed_in':_session is not None,'email':_session['email'] if _session else None}
  if action=='recover':
   email=str(body.get('email','')).strip()
   if '@' not in email or len(email)>254:raise ValueError('Enter your account email address.')
   _request('/auth/v1/recover',{'email':email})
   return {'message':'If this address has an account, a password reset email will arrive shortly. Check spam too.'}
  if action=='reset':
   # Recovery happens here, never on a public GitHub Pages password form.
   email=str(body.get('email','')).strip();code=str(body.get('code','')).strip()
   password=body.get('password','')
   if '@' not in email or len(email)>254 or not isinstance(password,str) or not 8<=len(password)<=1024:
    raise ValueError('Enter your account email and a new password of at least eight characters.')
   if code.isascii() and code.isdigit() and 6<=len(code)<=10:
    proof={'email':email,'token':code,'type':'recovery'}
   else:
    link=urllib.parse.urlsplit(code);query=urllib.parse.parse_qs(link.query)
    if link.scheme!='https' or link.netloc!=urllib.parse.urlsplit(URL).netloc or link.path!='/auth/v1/verify' or query.get('type')!=['recovery'] or len(query.get('token',[]))!=1 or link.fragment:
     raise ValueError('Paste the recovery code or copy the unopened password-reset link from your email.')
    proof={'token_hash':query['token'][0],'type':'recovery'}
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
   _session=None
   return {'signed_in':False,'message':'Password updated. Sign in with your new password.'}
  if action=='delete':
   if not _session:raise ValueError('Sign in before deleting your account.')
   if body.get('confirmation')!='DELETE':raise ValueError('Type DELETE to confirm account deletion.')
   _request('/rest/v1/rpc/bandstand_delete_own_account',{},_session['token'])
   _session=None
   return {'signed_in':False,'message':'Account and consent record deleted. Local recordings remain on this computer.'}
  if action=='signout':
   previous=_session;_session=None
   if previous:
    try:_request('/auth/v1/logout',{},previous['token'])
    except ValueError:pass
   return {'signed_in':False}
  if action not in ('signin','signup'):raise ValueError('Unknown account action')
  email=str(body.get('email','')).strip();password=body.get('password','')
  if '@' not in email or len(email)>254 or not isinstance(password,str) or not 8<=len(password)<=1024:
   raise ValueError('Enter your email and a password of at least eight characters.')
  _session=None
  result=_request('/auth/v1/signup' if action=='signup' else '/auth/v1/token?grant_type=password',{'email':email,'password':password})
  if result.get('access_token'):
   user=_request('/auth/v1/user',token=result['access_token'])
   _session={'token':result['access_token'],'email':user['email'],'user_id':user['id']}
   return {'signed_in':True,'email':user['email']}
  return {'signed_in':False,'message':'Check your email to confirm your account, then sign in.'}
