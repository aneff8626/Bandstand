"""Shared native/browser session listing and explicit local deletion."""
import json,re,shutil,time
from pathlib import Path
from contextlib import nullcontext

def saved_sessions(root):
 rows=[]
 for p in sorted(Path(root).glob('*/session.json'),reverse=True):
  if p.parent.is_symlink():continue
  s=json.loads(p.read_text());row={k:s.get(k) for k in ['id','title','source','started','ended','running','mode','protocol']}
  path=p.parent/'trials.json'
  if path.exists():
   trials=json.loads(path.read_text());total=len(trials);usable=sum(any(v.get('accepted') for v in (t.get('channel_trials') or t.get('spectral_channels') or {}).values()) if (t.get('channel_trials') or t.get('spectral_channels')) else bool(t.get('accepted')) for t in trials)
   if s.get('mode')=='tf':
    usable=total=0
    for trial in trials:
     windows={}
     for channel in trial.get('spectral_channels',{}).values():
      for w in channel.get('windows',[]):
       key=(w['start'],w['end']);windows[key]=windows.get(key,False) or w.get('power') is not None
     previous=-float('inf')
     for (start,end),good in sorted(windows.items()):
      if start>=previous-1e-6:total+=1;usable+=int(good);previous=end
   row['quality_metrics']={'usable':usable,'total':total}
  rows.append(row)
 return rows

def delete_session(engine,body,root):
 root=Path(root).resolve();ident=body.get('id');kind=body.get('kind')
 if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}',ident) or body.get('confirmation')!=ident:raise ValueError('Confirm the specific session to delete.')
 if kind not in ('personal','lab','writing'):raise ValueError('Unknown session type')
 with engine.lock:
  for active in [getattr(engine,'session',None),getattr(engine.personal,'current',None),getattr(engine.typing,'session',None) if engine.typing.running else None]:
   if active and active.get('id')==ident and active.get('running',True):raise ValueError('Stop this recording before deleting it.')
  if kind=='writing' and (engine.typing.running or engine.typing.fitting):raise ValueError('Wait for typing recording and model evaluation to stop before deleting writing data.')
  targets=[]
  if kind=='personal':
   for p in (root/'personal').glob('record-*.json'):
    if json.loads(p.read_text()).get('id')==ident:
     r=json.loads(p.read_text());targets.append(p)
     raw=r.get('raw_eeg_file')
     if raw:
      if Path(raw).name!=raw:raise ValueError('Invalid recording path')
      targets.append(root/'personal'/raw)
   if not targets:raise ValueError('Session not found')
   targets.append(root/'personal'/f'spectral-{ident}.json')
   active=root/'personal'/'active.json'
   if active.exists() and json.loads(active.read_text()).get('id')==ident:targets.append(active)
  else:
   folder=root/('typing' if kind=='writing' else '')/ident
   if folder.is_symlink() or (folder/'session.json').is_symlink():raise ValueError('Invalid recording path')
   if not (folder/'session.json').is_file() or json.loads((folder/'session.json').read_text()).get('id')!=ident:raise ValueError('Session not found')
   targets.append(folder)
  caches=[]
  if kind=='writing':
   caches=[root/'typing'/name for name in ['semantic_checkpoint.npz','semantic_archive.sqlite3','semantic_archive.sqlite3-wal','semantic_archive.sqlite3-shm','semantic_request.json','semantic_result.json','decoder_review.json','evaluation_history.jsonl','shared_learning_contract.json']]
  # Reject links rather than following them to another session or outside local storage.
  for target in targets+caches:
   if target.is_symlink() or root not in target.resolve().parents:raise ValueError('Invalid recording path')
  try:import erp_outbox
  except ImportError:erp_outbox=None
  with erp_outbox._lock if erp_outbox else nullcontext():
   if erp_outbox and kind=='lab':
    pending=[i for i in erp_outbox.items() if i['session']==ident]
    if any(i['state']=='uploading' for i in pending):raise ValueError('An upload is in progress. Wait for it to finish before deleting locally.')
    for item in pending:
     if item['state'] in ('pending','failed'):erp_outbox._set(item,'withdrawn',time.time(),error='Local recording deleted.')
   for target in targets:
    if target.is_dir():shutil.rmtree(target)
    else:target.unlink(missing_ok=True)
  for p in (root/'participant-context').glob('*.json'):
   if not p.is_symlink() and json.loads(p.read_text()).get('session_id')==ident:p.unlink()
  # Exports made by this app include the session identifier; external copies are untouched.
  for p in (root/'exports').glob('*'):
   if p.is_file() and not p.is_symlink() and ident in p.name:p.unlink()
  if kind=='writing':
   for p in caches:p.unlink(missing_ok=True)
   from typing_lab import TypingLab
   engine.typing=TypingLab(root.parent,data_dir=root)
  if kind=='lab' and getattr(engine,'session',{} ) and engine.session.get('id')==ident:
   engine.session=None;engine.trials=[];engine.pending=[];engine.cache_revision=-1
  return {'deleted':True,'scope':'local','id':ident}
