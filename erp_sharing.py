"""Construct numeric ERP trial exports; never upload arbitrary session files."""
import json,math,uuid
from private_storage import DATA_ROOT
CHANNELS=('TP9','AF7','AF8','TP10')
APP_VERSION='0.3.0-alpha.1'
# The schema the client sends. v2 adds recording metadata (versions, filters, windows, completion, rejection
# categories) that the current ERP sharing notice does not list; switch to v2 only after that notice is updated.
SCHEMA='bandstand-erp-v1'
SCHEMAS=('bandstand-erp-v1','bandstand-erp-v2')
# Rejection reasons become fixed categories; the wording itself never leaves the device.
REJECTION={'data loss':'missing','data loss / electrode stream missing':'missing','signal clipping':'clipping','flat signal / probable poor contact':'flatline',
 'large EEG transient / possible contact noise':'transient','probable blink':'blink','probable muscle artifact':'muscle',
 'uncertain event timing':'timing','presentation timing interrupted':'timing'}
def end_category(reason):return 'completed' if reason=='completed' else 'stopped' if reason=='stopped by participant' else 'interrupted'
def payload(ident,schema=None):
 schema=schema or SCHEMA
 if schema not in SCHEMAS:raise ValueError('Unknown ERP sharing schema')
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
   if v:
    channels[c]={'accepted':v.get('accepted') is True,'wave':numbers(v['wave']) if v.get('wave') is not None else None}
    if schema=='bandstand-erp-v2':channels[c]['rejection']=sorted({REJECTION.get(r,'other') for r in v.get('reasons') or [] if isinstance(r,str)})
  trials.append({'condition':t['condition_index'],'times':numbers(t['times']),'channels':channels})
 result={'schema':schema,'protocol':session['protocol'],'trials':trials}
 if schema=='bandstand-erp-v2':
  times=trials[0]['times'];window=session.get('window')
  if not (isinstance(window,list) and len(window)==2 and all(type(w) in (int,float) and math.isfinite(w) for w in window)):raise ValueError('Invalid analysis window')
  planned=session.get('trials_planned')
  result['recording']={'app_version':APP_VERSION,'sample_rate_hz':256,'units':'uV','reference':'TP9-TP10-mean' if session['protocol']=='reward' else 'FPz',
   'channels':[c for c in CHANNELS if c in (session.get('channels') or [])],'preprocessing':'causal-hp0.1-lp30-notch60q30','grid':'interpolated-256hz',
   'epoch_s':[times[0],times[-1]],'baseline_s':[times[0],0],'analysis_window_s':[float(window[0]),float(window[1])],
   'trials_planned':planned if type(planned) is int and 0<planned<=10000 else len(trials),'trials_presented':len(trials),'end':end_category(session.get('end_reason'))}
 if len(json.dumps(result))>10000000:raise ValueError('Recording exceeds sharing limit')
 return str(uuid.uuid5(uuid.NAMESPACE_URL,'bandstand-erp:'+ident)),result
