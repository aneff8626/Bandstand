"""Durable outbox for consented ERP uploads. Stores status only; the numeric payload is rebuilt from the local
recording at upload time, so no second copy of EEG is kept.

Every item is bound to the account and consent policy that queued it. An item uploads only while that same
account is signed in and the server still reports consent; another account's session never sends it.
Withdrawal stops pending items at once. Nothing is backfilled: items exist only for recordings queued when
they finished."""
import json,os,threading,time,uuid
from private_storage import DATA_ROOT
ROOT=DATA_ROOT/'erp-outbox'
STATES=('pending','uploading','uploaded','failed','withdrawn')
MAX_ATTEMPTS=8
_lock=threading.RLock()

def _path(item_id):
 if not isinstance(item_id,str):raise ValueError('Invalid outbox item')
 uuid.UUID(item_id);return ROOT/f'{item_id}.json'

def _write(item):
 ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
 path=_path(item['id']);temp=path.with_suffix('.tmp')
 temp.write_text(json.dumps(item));temp.chmod(0o600);os.replace(temp,path)

def _read(path):
 try:return json.loads(path.read_text())
 except (OSError,ValueError):return None

def items():
 with _lock:
  if not ROOT.exists():return []
  return [i for i in (_read(p) for p in sorted(ROOT.glob('*.json'))) if i and i.get('state') in STATES]

def enqueue(item_id,session_id,user_id,policy,now=None):
 """Queue one finished recording for the consenting account. Idempotent: an existing item is left alone."""
 now=time.time() if now is None else now
 with _lock:
  path=_path(item_id)
  if path.exists() and _read(path):return _read(path)
  item={'id':item_id,'session':session_id,'user':user_id,'policy':policy,'state':'pending','attempts':0,'next_at':now,'created':now,'updated':now,'error':''}
  _write(item);return item

def backoff(attempts):return min(30*2**max(attempts-1,0),3600)

def _set(item,state,now,**changes):
 item.update(state=state,updated=now,**changes);_write(item);return item

def recover(now=None):
 """After a crash or restart, an interrupted upload returns to pending; the server ignores duplicates."""
 now=time.time() if now is None else now
 with _lock:
  for item in items():
   if item['state']=='uploading':_set(item,'pending',now,next_at=now)

def withdraw(user_id,now=None):
 now=time.time() if now is None else now
 with _lock:
  for item in items():
   if item['user']==user_id and item['state'] in ('pending','uploading','failed'):_set(item,'withdrawn',now,error='Consent withdrawn before upload.')

def forget(user_id):
 with _lock:
  for item in items():
   if item['user']==user_id:_path(item['id']).unlink(missing_ok=True)

def retry(user_id,now=None):
 now=time.time() if now is None else now
 with _lock:
  for item in items():
   if item['user']==user_id and item['state']=='failed':_set(item,'pending',now,attempts=0,next_at=now,error='')

def summary(user_id):
 counts={s:0 for s in STATES};other=0
 for item in items():
  if item['user']==user_id:counts[item['state']]+=1
  elif item['state'] in ('pending','uploading'):other+=1
 return {**counts,'held_for_other_account':other}

def process(user_id,consent,upload,now=None):
 """One pass over due items of the signed-in account. consent() returns the server's current answer;
 upload(item) sends the rebuilt payload and raises TransientError (retry later) or ValueError (give up)."""
 now=time.time() if now is None else now
 with _lock:
  due=[i for i in items() if i['user']==user_id and i['state']=='pending' and i['next_at']<=now]
 if not due:return 0
 try:allowed=consent()
 except TransientError:return 0
 sent=0
 for item in due:
  with _lock:
   current=_read(_path(item['id']))
   if not current or current['state']!='pending':continue
   if not allowed:_set(current,'withdrawn',now,error='Sharing is turned off for this account.');continue
   _set(current,'uploading',now)
  try:upload(current)
  except TransientError:
   with _lock:
    attempts=current['attempts']+1
    if attempts>=MAX_ATTEMPTS:_set(current,'failed',now,attempts=attempts,error='The account server could not be reached after repeated attempts.')
    else:_set(current,'pending',now,attempts=attempts,next_at=now+backoff(attempts),error='Waiting to retry: the account server could not be reached.')
  except ValueError as e:
   with _lock:_set(current,'failed',now,attempts=current['attempts']+1,error=str(e)[:200])
  else:
   with _lock:_set(current,'uploaded',now,uploaded=now,error='');sent+=1
 return sent

class TransientError(Exception):
 """Network failure, timeout, rate limit or server error: try again later."""
