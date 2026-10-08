"""Construct numeric ERP trial exports; never upload arbitrary session files."""
import json,math,uuid
from private_storage import DATA_ROOT
CHANNELS=('TP9','AF7','AF8','TP10')
def payload(ident):
 if not ident or any(c not in '0123456789-abcdef' for c in ident):raise ValueError('Invalid recording')
 folder=DATA_ROOT/ident
 if folder.is_symlink():raise ValueError('Invalid recording folder')
 session=json.loads((folder/'session.json').read_text())
 if session.get('running') or session.get('mode')!='erp' or session.get('source')!='live' or session.get('protocol') not in ('oddball','auditory','flanker','reward'):raise ValueError('Only completed built-in ERP recordings can be shared.')
 def numbers(values):
  if not isinstance(values,list) or len(values)>1024:raise ValueError('Invalid ERP array')
  if any(type(v) not in (float,int) or not math.isfinite(v) for v in values):raise ValueError('Invalid ERP samples')
  return values
 trials=[]
 source=json.loads((folder/'trials.json').read_text())
 if not source or len(source)>10000:raise ValueError('No shareable ERP trials')
 for t in source:
  if type(t.get('condition_index')) is not int or t['condition_index'] not in (0,1):raise ValueError('Invalid condition')
  channels={}
  for c in CHANNELS:
   v=t.get('channel_trials',{}).get(c)
   if v:channels[c]={'accepted':v.get('accepted') is True,'wave':numbers(v['wave']) if v.get('wave') is not None else None}
  trials.append({'condition':t['condition_index'],'times':numbers(t['times']),'channels':channels})
 result={'schema':'bandstand-erp-v1','protocol':session['protocol'],'trials':trials}
 if len(json.dumps(result))>10000000:raise ValueError('Recording exceeds sharing limit')
 return str(uuid.uuid5(uuid.NAMESPACE_URL,'bandstand-erp:'+ident)),result
