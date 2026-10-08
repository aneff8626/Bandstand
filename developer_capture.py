"""Local labeled examples for developer review; does not train automatically."""
import time, json, uuid
from pathlib import Path
import numpy as np
from analysis import CHANNELS, FS, artifacts

ACTIONS={
 'free_recording':'Unlabeled recording. The participant will describe the action afterward.',
 'tongue_movement':'Move your tongue gently left and right inside your closed mouth. Keep your jaw, head and eyes still.',
 'jaw_clench':'Gently clench your jaw for one second, relax for one second, and repeat. Keep your head and eyes still.',
 'saccade':'Keep your head still. Alternate your gaze between the left and right targets, about once per second.',
 'blink':'Look at the center target. Blink once every two seconds; relax your jaw and keep your head still.',
 'head_rotation':'Slowly turn your head left and right within a comfortable range. Keep your jaw relaxed.',
 'look_up_down':'Keep your head still. Alternate your gaze between the upper and lower targets, about once per second.'}

def cue_plan(action,onset):
 if action=='free_recording':return []
 if action=='blink':
  return [dict(index=i,onset=onset+i, label=('Blink '+str(i//2+1)+' / 10') if i%2==0 else 'Eyes open · relax',target='center') for i in range(20)]
 pairs={'look_up_down':('Look UP','Look DOWN','up','down'),'saccade':('Look LEFT','Look RIGHT','left','right'),'jaw_clench':('Gently CLENCH','RELAX','center','center'),'tongue_movement':('Tongue LEFT','Tongue RIGHT','center','center'),'head_rotation':('Turn head LEFT','Turn head RIGHT','center','center')}
 labels=pairs[action]
 return [dict(index=i,onset=onset+i,label=labels[i%2],target=labels[2+i%2] if action in ('look_up_down','saccade') else 'center') for i in range(20)]

class DeveloperCapture:
 def __init__(self,root,data_dir=None):
  self.root=(Path(data_dir) if data_dir is not None else Path(root)/'data')/'developer';self.current=None;self.rows=[];self.motion=[];self.last=None
 def start(self,action,source,running=False):
  if running:raise ValueError('Finish the experiment before developer calibration.')
  if self.current:raise ValueError('A calibration example is already recording.')
  if source!='live':raise ValueError('Developer calibration requires live headset data.')
  if action not in ACTIONS:raise ValueError('Choose a supported action.')
  start=time.time();self.rows=[];self.motion=[]
  self.current=dict(id=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6],action=action,source=source,started=start,action_onset=start+8,ends=start+28,instruction=ACTIONS[action])
  if action=='free_recording':self.current.update(action_onset=start,ends=start+600)
  self.current['cues']=cue_plan(action,self.current['action_onset']);self.current['displayed_cues']=[]
  self.root.mkdir(parents=True,exist_ok=True)
  (self.root/(self.current['id']+'.pending.json')).write_text(json.dumps(self.current,indent=2))
  return self.status()
 def cue(self,body):
  c=self.current
  if not c or body.get('capture_id')!=c['id']:return {'ok':False}
  i=body.get('index')
  if not isinstance(i,int) or not 0<=i<len(c['cues']):raise ValueError('Invalid cue index')
  if not any(v['index']==i for v in c['displayed_cues']):
   c['displayed_cues'].append(dict(index=i,displayed_at=float(body['displayed_at']),received_at=time.time(),planned_at=c['cues'][i]['onset'],label=c['cues'][i]['label']))
  return {'ok':True}
 def add(self,times,raw,filtered):
  if not self.current:return
  for t,r,f in zip(times,raw,filtered):
   if self.current['started']<=t<=self.current['ends']:self.rows.append([float(t),*r,*f])
 def add_motion(self,body):
  if self.current:self.motion.append(body)
 def status(self):
  if self.current and time.time()>=self.current['ends']:self.finish()
  c=self.current
  return dict(recording=bool(c),capture=c,phase=('rest' if time.time()<c['action_onset'] else 'action') if c else None,remaining=max(0, (c['action_onset'] if time.time()<c['action_onset'] else c['ends'])-time.time()) if c else 0,last=self.last)
 def finish(self,cancel=False):
  if not self.current:return self.last
  c=self.current;self.current=None
  if c['action']=='free_recording':c['ends']=min(c['ends'],time.time())
  x=np.asarray(self.rows,float).reshape(-1,9)
  summary={**c,'requested_action':c['action'],'cancelled':cancel,'samples':len(x),'channels':CHANNELS,'timing':'Software cue; labels describe requested actions, not verified behavior. BLE receive-anchored EEG clock.'}
  for name,start,end in [('rest',c['started'],c['action_onset']),('action',c['action_onset'],c['ends'])]:
   seg=x[(x[:,0]>=start)&(x[:,0]<end)] if len(x) else x
   metrics={'samples':len(seg),'expected_samples':round((end-start)*FS),'usable':len(seg)>1 and end>start and len(seg)>=.9*(end-start)*FS and bool(np.isfinite(seg).all()) and not bool(np.any(np.diff(seg[:,0])>1.75/FS))}
   if metrics['usable']:
    raw=seg[:,1:5];center=raw-raw.mean(0);freq=np.fft.rfftfreq(len(raw),1/FS);spectrum=np.abs(np.fft.rfft(center,axis=0))**2
    metrics.update(peak_to_peak_uv=np.ptp(raw,axis=0).tolist(),std_uv=np.std(raw,axis=0).tolist(),high_frequency_fraction=(spectrum[(freq>=25)&(freq<=45)].sum(0)/np.maximum(spectrum[(freq>=1)&(freq<=45)].sum(0),1e-12)).tolist(),frontal_correlation=float(np.corrcoef(raw[:,1:3].T)[0,1]) if np.min(np.std(raw[:,1:3],axis=0))>0 else None,detector_flags=artifacts(raw,seg[:,0]),gaps=int(np.sum(np.diff(seg[:,0])>1.75/FS)))
   summary[name]=metrics
  if summary['rest']['usable'] and summary['action']['usable']:
   summary['std_ratio_action_to_rest']=(np.asarray(summary['action']['std_uv'])/np.maximum(summary['rest']['std_uv'],1e-6)).tolist()
  from live_artifacts import detect_events
  summary['artifact_annotations']=[]
  for start in range(0,len(x)-FS//2+1,FS//2):
   block=x[start:start+FS//2]; summary['artifact_annotations'].extend(detect_events(block[:,1:5],block[:,0]))
  dest=self.root/c['id'];np.savez_compressed(str(dest)+'.npz',times=x[:,0],raw=x[:,1:5],filtered=x[:,5:9])
  Path(str(dest)+'.motion.json').write_text(json.dumps(self.motion))
  Path(str(dest)+'.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
  pending=self.root/(c['id']+'.pending.json')
  if pending.exists():pending.unlink()
  self.last={**summary,'file':str(dest)+'.json'};return self.last
