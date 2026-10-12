"""Channel-local spectral windows; block-level inference, never overlapping-window n."""
import numpy as np
from analysis import FS,CHANNELS,artifacts,spectrum,compare,summarize

def channel_windows(raw,notched,times,window,thresholds):
 t=np.asarray(times);raw=np.asarray(raw);notched=np.asarray(notched)
 result={}
 for ch,name in enumerate(CHANNELS):
  windows=[];covered=set()
  for start in np.arange(window[0],window[1]-2+1e-6,.5):
   ids=np.flatnonzero((t>=start-1e-6)&(t<start+2-1e-6));reasons=[]
   if len(ids)<2*FS-2 or not len(ids) or t[ids[0]]>start+2/FS or t[ids[-1]]<start+2-2/FS:reasons=['incomplete window / data loss']
   else:reasons=artifacts(raw[ids],t[ids],thresholds,[ch])
   if not reasons and not np.isfinite(notched[ids,ch]).all():reasons=['filtered data missing']
   power=None
   if not reasons:
    grid=start+np.arange(2*FS)/FS
    freq,p=spectrum(np.interp(grid,t[ids],notched[ids,ch])[:,None]);sel=(freq>=2)&(freq<=40);power=p[sel,0].tolist();covered.update(ids.tolist())
   windows.append(dict(start=float(start),end=float(start+2),power=power,reasons=reasons))
  seconds=len(covered)/FS;good=[w['power'] for w in windows if w['power'] is not None]
  result[name]=dict(accepted=seconds>=4,clean_seconds=seconds,windows=windows,preview_psd=good[-1] if good else None,psd=np.mean(good,axis=0).tolist() if good and seconds>=4 else None,reasons=[] if seconds>=4 else ['Fewer than 4 clean seconds']+list(dict.fromkeys(r for w in windows for r in w['reasons'])))
 return result

def summarize_tf(trials,session,band):
 frequencies=np.arange(2,40.01,.5);weights=np.maximum(0,np.minimum(frequencies+.25,band[1])-np.maximum(frequencies-.25,band[0]));channels={};rejections=[]
 for name in CHANNELS:
  groups=[];rejected=[]
  for ci,label in enumerate(session['conditions']):
   rows=[(t,t.get('spectral_channels',{}).get(name)) for t in trials if t['condition_index']==ci];rows=[(t,r) for t,r in rows if r]
   good=[r for _,r in rows if r['accepted']];features=[float(10*np.log10(max(np.sum(np.asarray(r['psd'])*weights),1e-12))) for r in good]
   psds=[(10*np.log10(np.maximum(r['psd'],1e-12))).tolist() for r in good]
   segment_features=[]
   for _,row in rows:
    end=-float('inf')
    for w in row['windows']:
     if w['power'] is not None and w['start']>=end-1e-6:
      segment_features.append(float(10*np.log10(max(np.sum(np.asarray(w['power'])*weights),1e-12))))
      end=w['end']

   window_times=sorted(set(round((w['start']+w['end'])/2,4) for _,r in rows for w in r['windows']))
   columns=[]
   for center in window_times:
    powers=[w['power'] for _,r in rows for w in r['windows'] if w['power'] is not None and abs((w['start']+w['end'])/2-center)<1e-5]
    columns.append((10*np.log10(np.maximum(np.mean(powers,axis=0),1e-12))).tolist() if powers else [None]*len(frequencies))
   tf=dict(times=window_times,frequencies=frequencies.tolist(),power_db=list(map(list,zip(*columns))) if columns else [])
   groups.append(dict(segment_features=segment_features,tf=tf,label=label,accepted=len(good),rejected=len(rows)-len(good),clean_seconds=sum(r['clean_seconds'] for _,r in rows),features=features,mean=float(np.mean(features)) if features else None,se=float(np.std(features,ddof=1)/np.sqrt(len(features))) if len(features)>1 else None,psd=summarize(psds) if psds else None))
   for trial,row in rows:
    if not row['accepted']:rejected.append(dict(index=trial['index'],condition=label,reasons=row['reasons']))
    for w in row['windows']:
     if w['reasons']:rejections.append(dict(channel=name,index=trial['index'],condition=label,reasons=[f"{w['start']:g}–{w['end']:g} s: "+', '.join(w['reasons'])]))
  if session.get('protocol')=='disclosure':
   for g in groups:
    g['features']=g['segment_features'];g['accepted']=len(g['features']);g['mean']=float(np.mean(g['features'])) if g['features'] else None;g['se']=float(np.std(g['features'],ddof=1)/np.sqrt(len(g['features']))) if len(g['features'])>1 else None
  channels[name]=dict(groups=groups,stats=compare(groups[0]['features'],groups[1]['features'],session['minimum']),unit='dB re 1 µV²',rejections=rejected)
 return dict(clip_inference=session.get('protocol')=='disclosure',channels=channels,groups=[],frequencies=frequencies.tolist(),band=band,trial_count=len(trials),pending=0,times=[],stats=dict(ready=False,reason='See individual electrode comparisons'),rejections=rejections,unit='dB re 1 µV²',spectral=True)
