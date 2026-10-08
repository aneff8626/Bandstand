"""Personal calibration heuristics, explicitly uncertain; not a validated classifier."""
import numpy as np
from analysis import CHANNELS,FS

def features(x):
 x=np.asarray(x,float)
 if not np.isfinite(x).all():return None
 y=x-x.mean(0);freq=np.fft.rfftfreq(len(x),1/FS)
 p=np.abs(np.fft.rfft(y*np.hanning(len(x))[:,None],axis=0))**2
 hf=p[(freq>=25)&(freq<=45)].sum(0)/np.maximum(p[(freq>=1)&(freq<=45)].sum(0),1e-9)
 smooth=np.stack([np.convolve(x[:,i],np.ones(9)/9,'valid') for i in range(4)],axis=1)
 def corr(a,b):return float(np.corrcoef(a,b)[0,1]) if min(np.std(a),np.std(b))>1 else 0.
 return dict(ptp=np.ptp(x,axis=0),std=np.std(x,axis=0),hf=hf,frontal=corr(smooth[:,1],smooth[:,2]),temporal=corr(smooth[:,0],smooth[:,3]))

def classify(x,t,profile,motion=None):
 if profile.get('version',1)>=2:return classify_v2(x,t,profile,motion)
 f=features(x)
 if f is None or np.any(np.abs(x)>=995):return []
 p,h=f['ptp'],f['hf'];rules=profile['rules'];events=[]
 def event(label,channels,kind,measure=None):
  idx=np.arange(len(t))
  if measure is not None:
   candidate=np.flatnonzero(measure>max(float(np.max(measure))*.3,15))
   if len(candidate):idx=candidate
  return dict(label=label,channels=channels,kind=kind,onset=float(t[idx[0]]),offset=float(t[idx[-1]]),uncertain=True,evidence='personal calibration v1')
 jaw=p[1]>rules['jaw_af7_ptp'] and h[1]>rules['jaw_hf'] and f['std'][1]>20 and h[2]>.12
 if jaw:
  channels=[CHANNELS[i] for i in range(4) if h[i]>.12 and p[i]>60]
  events.append(event('Jaw clench / facial tension',channels,'noise'))
 else:
  centered=x-np.median(x[:8],axis=0)
  if min(p[0],p[3])>rules['blink_temporal_ptp'] and f['temporal']>rules['blink_temporal_corr'] and min(p[0],p[3])>1.6*max(p[1],p[2]) and max(h[0],h[3])<.08:
   events.append(event('Blink',CHANNELS[:],'ocular',np.abs((centered[:,0]+centered[:,3])/2)))
  elif f['frontal']<rules['saccade_corr'] and p[1]>65 and p[2]>25 and h[1]<.10:
   events.append(event('Horizontal saccade',['AF7','AF8'],'ocular',np.abs((centered[:,1]-centered[:,2])/2)))
  elif f['frontal']>.65 and p[1]>70 and p[2]>35 and max(h[1],h[2])<.12:
   events.append(event('Vertical eye movement',['AF7','AF8'],'ocular',np.abs((centered[:,1]+centered[:,2])/2)))
 if motion and motion.get('gyro') is not None and motion['gyro']>rules['head_rotation_dps']:
  affected=[CHANNELS[i] for i in range(4) if p[i]>profile['rest_ptp_median'][i]*1.4]
  if affected:events.append(event('Head rotation',affected,'noise'))
 return events


def slow_features(x):
 """Separate slow spatial patterns from fast noise without altering displayed EEG."""
 x=np.asarray(x,float)
 slow=np.stack([np.convolve(np.pad(x[:,i],(16,16),mode='reflect'),np.ones(33)/33,'valid') for i in range(4)],axis=1)
 def corr(i,j):
  return float(np.corrcoef(slow[:,i],slow[:,j])[0,1]) if min(np.std(slow[:,i]),np.std(slow[:,j]))>1 else 0.
 return slow,np.ptp(slow,axis=0),dict(temporal=corr(0,3),frontal=corr(1,2),left_temporal_frontal=corr(0,1))


def expected_frontal_blink(x):
 """A matched, brief frontal pulse returning toward baseline; provisional without EOG."""
 f=features(x)
 if f is None or max(f['hf'][1:3])>.2:return False
 smooth=np.stack([np.convolve(x[:,i],np.ones(9)/9,'valid') for i in (1,2)],axis=1)
 smooth-=np.median(smooth[:8],axis=0)
 amplitudes=np.max(np.abs(smooth),axis=0)
 if min(amplitudes)<45 or max(amplitudes)<80 or min(np.std(smooth,axis=0))<5:return False
 common=np.mean(smooth,axis=1);peak=int(np.argmax(np.abs(common)))
 return bool(np.corrcoef(smooth.T)[0,1]>.75 and 8<peak<len(smooth)-8 and np.max(np.abs(np.median(smooth[-8:],axis=0)))<max(amplitudes)*.45)


def classify_v2(x,t,profile,motion=None):
 x=np.asarray(x,float);t=np.asarray(t,float)
 if len(x)<33 or not np.isfinite(x).all() or np.any(np.diff(t)>1.75/FS):return []
 # Clipping cannot be repaired by smoothing. Preserve severe channel flags downstream.
 if np.any(np.abs(x)>=995):return []
 slow,p,c=slow_features(x);f=features(x);r=profile['rules'];events=[]
 centered=slow-np.median(slow[:8],axis=0)
 def event(label,channels,kind,measure=None):
  idx=np.arange(len(t))
  if measure is not None:
   candidate=np.flatnonzero(measure>max(float(np.max(measure))*.3,8))
   if len(candidate):idx=candidate
  return dict(label=label,channels=channels,kind=kind,onset=float(t[idx[0]]),offset=float(t[idx[-1]]),uncertain=True,evidence='personal calibration v2')
 # A single noisy channel was repeatedly mistaken for jaw tension during quiet rest.
 # Keep that channel marked even when a slow ocular pattern is also present.
 raw_ptp=f['ptp'];isolated=[]
 for i in range(4):
  peers=np.delete(raw_ptp,i)
  if raw_ptp[i]>r['isolated_noise_ptp'] and f['hf'][i]>r['isolated_noise_hf'] and raw_ptp[i]>r['isolated_noise_ratio']*max(float(np.median(peers)),20):isolated.append(CHANNELS[i])
 if isolated:events.append(event('Channel noise',isolated,'noise'))
 temporal=min(p[0],p[3]);front_temporal=c['left_temporal_frontal']
 blink=(temporal>r['blink_slow_temporal_ptp'] and c['temporal']>r['blink_temporal_corr'] and front_temporal<r['blink_front_temporal_corr'] and p[1]>r['blink_slow_af7_ptp'] and p[2]<temporal*r['blink_af8_ratio'])
 tongue=(temporal>r['tongue_slow_temporal_ptp'] and c['temporal']>r['tongue_temporal_corr'] and front_temporal>r['tongue_front_temporal_corr'] and p[1]<r['tongue_af7_max'] and p[2]<r['tongue_af8_max'] and temporal>p[1]*r['tongue_temporal_ratio'])
 # Restore the expected frontal pulse and the earlier temporal-dominant pattern.
 # Do not require the newer AF7 polarity/size pattern for every blink.
 frontal_blink=expected_frontal_blink(x)
 legacy_temporal=(min(raw_ptp[0],raw_ptp[3])>250 and f['temporal']>.94 and min(raw_ptp[0],raw_ptp[3])>1.6*max(raw_ptp[1],raw_ptp[2]) and max(f['hf'][0],f['hf'][3])<.08 and not tongue)
 if blink or frontal_blink or legacy_temporal:
  measure=np.abs((centered[:,1]+centered[:,2])/2) if frontal_blink else np.abs((centered[:,0]+centered[:,3])/2)
  events.append(event('Blink',CHANNELS[:],'ocular',measure))
 elif tongue:
  events.append(event('Muscle activity',['TP9','TP10'],'noise',np.abs((centered[:,0]+centered[:,3])/2)))
 elif c['frontal']<r['horizontal_corr'] and p[1]>r['horizontal_af7_ptp'] and p[2]>r['horizontal_af8_ptp'] and temporal<r['horizontal_temporal_max']:
  events.append(event('Horizontal saccade',['AF7','AF8'],'ocular',np.abs((centered[:,1]-centered[:,2])/2)))
 elif c['frontal']>r['vertical_corr'] and p[1]>r['vertical_af7_ptp'] and p[2]>r['vertical_af8_ptp']:
  events.append(event('Vertical eye movement',['AF7','AF8'],'ocular',np.abs((centered[:,1]+centered[:,2])/2)))
 # No accepted new jaw/head examples exist; keep muscle generic and require the IMU for head rotation.
 if motion and motion.get('gyro') is not None and motion['gyro']>r['head_rotation_dps']:
  affected=[CHANNELS[i] for i in range(4) if p[i]>max(50,profile['rest_slow_ptp_median'][i]*2) and CHANNELS[i] not in isolated]
  if affected:events.append(event('Head rotation',affected,'noise'))
 return events
