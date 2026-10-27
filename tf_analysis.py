"""Channel-local spectral windows; block-level inference, never overlapping-window n."""
import numpy as np
from analysis import FS,CHANNELS,artifacts,spectrum,compare,summarize
from spectral_inference import compare_periods

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
 if band[0]==band[1]:weights[:]=0;weights[int(np.argmin(abs(frequencies-band[0])))]=.5
 for name in CHANNELS:
  groups=[];rejected=[]
  for ci,label in enumerate(session['conditions']):
   rows=[(t,t.get('spectral_channels',{}).get(name)) for t in trials if t['condition_index']==ci];rows=[(t,r) for t,r in rows if r]
   good=[r for _,r in rows if r['accepted']];features=[float(10*np.log10(max(np.sum(np.asarray(r['psd'])*weights),1e-12))) for r in good]
   psds=[(10*np.log10(np.maximum(r['psd'],1e-12))).tolist() for r in good]
   segment_features=[];runs=[];blocks=[]
   for trial,row in rows:
    end=-float('inf');run=[];block_values=[]
    for w in row['windows']:
     if w['power'] is not None and w['start']>=end-1e-6:
      value=float(10*np.log10(max(np.sum(np.asarray(w['power'])*weights),1e-12)))
      if run and w['start']>end+1e-6:runs.append(run);run=[]
      run.append(value);block_values.append(value);segment_features.append(value);end=w['end']
    if run:runs.append(run)
    blocks.append(dict(index=trial['index'],partial=trial.get('partial',False),features=block_values,mean=float(np.mean(block_values)) if block_values else None,sd=float(np.std(block_values,ddof=1)) if len(block_values)>1 else None,psd=(10*np.log10(np.maximum(row['psd'],1e-12))).tolist() if row.get('psd') is not None else None))

   window_times=sorted(set(round((w['start']+w['end'])/2,4) for _,r in rows for w in r['windows']))
   columns=[]
   for center in window_times:
    powers=[w['power'] for _,r in rows for w in r['windows'] if w['power'] is not None and abs((w['start']+w['end'])/2-center)<1e-5]
    columns.append((10*np.log10(np.maximum(np.mean(powers,axis=0),1e-12))).tolist() if powers else [None]*len(frequencies))
   tf=dict(times=window_times,frequencies=frequencies.tolist(),power_db=list(map(list,zip(*columns))) if columns else [])
   groups.append(dict(runs=runs,blocks=blocks,descriptive_mean=float(np.mean(segment_features)) if segment_features else None,sd=float(np.std(segment_features,ddof=1)) if len(segment_features)>1 else None,segment_features=segment_features,tf=tf,label=label,accepted=len(good),rejected=sum(not r['accepted'] and not t.get('partial',False) for t,r in rows),clean_seconds=sum(r['clean_seconds'] for _,r in rows),features=features,mean=float(np.mean(features)) if features else None,se=float(np.std(features,ddof=1)/np.sqrt(len(features))) if len(features)>1 else None,psd=summarize(psds) if psds else None))
   for trial,row in rows:
    if not row['accepted'] and not trial.get('partial',False):rejected.append(dict(index=trial['index'],condition=label,reasons=row['reasons']))
    for w in row['windows']:
     if w['reasons']:rejections.append(dict(channel=name,index=trial['index'],condition=label,reasons=[f"{w['start']:g}–{w['end']:g} s: "+', '.join(w['reasons'])]))
  pairwise=[]
  if len(groups)>2:
   for i in range(len(groups)):
    for j in range(i+1,len(groups)):
     pairwise.append(dict(labels=[groups[i]['label'],groups[j]['label']],**compare_periods(groups[i]['runs'],groups[j]['runs'])))
   ranked=sorted([p for p in pairwise if p['ready']],key=lambda p:p['p']);previous=0
   for rank,p in enumerate(ranked):
    previous=max(previous,min(1.,p['p']*(len(pairwise)-rank)));p['adjusted_p']=previous
  channels[name]=dict(groups=groups,stats=compare_periods(groups[0]['runs'],groups[1]['runs']) if len(groups)==2 else dict(ready=False,reason='Multiple conditions: descriptive estimates; no omnibus test'),unit='dB re 1 µV²',rejections=rejected,pairwise=pairwise)
 return dict(clip_inference=False,channels=channels,groups=[],frequencies=frequencies.tolist(),band=band,trial_count=len(trials),pending=0,times=[],stats=dict(ready=False,reason='See individual electrode comparisons'),rejections=rejections,unit='dB re 1 µV²',spectral=True)
