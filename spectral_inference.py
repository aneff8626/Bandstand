"""Exploratory inference conditional on recorded periods, not population/causal effects.
Non-overlapping 2 s log-power observations; moving chunks never cross gaps or blocks.
"""
import numpy as np
from functools import lru_cache

def bootstrap_periods(runs,draws=999,seed=1729):
 return _bootstrap_periods(tuple(tuple(float(v) for v in r) for r in runs if len(r)),draws,seed)

@lru_cache(maxsize=64)
def _bootstrap_periods(runs,draws,seed):
 runs=[np.asarray(r,dtype=float) for r in runs if len(r)]
 values=np.concatenate(runs) if runs else np.array([])
 result=dict(n=len(values),seconds=2*len(values),ready=False)
 if len(values)<12:return {**result,'reason':'Collect at least 24 usable seconds in this condition'}
 if not np.isfinite(values).all():return {**result,'reason':'Non-finite spectral values'}
 # Estimate dependence from within-run pairs only. No concatenation over artifact gaps.
 centered=[r-r.mean() for r in runs];variance=sum(float(r@r) for r in centered)
 if variance<1e-12:return {**result,'reason':'Too little within-period variation to estimate uncertainty'}
 length=min(max(3,int(np.ceil(len(values)**(1/3)))),max(2,min(map(len,runs))//2))
 strong_dependence=False
 for lag in range(1,min(max(map(len,runs)),len(values)//4+1)):
  pairs=[(r[:-lag],r[lag:]) for r in centered if len(r)>lag]
  denominator=sum(float(a@a+b@b)/2 for a,b in pairs)
  rho=sum(float(a@b) for a,b in pairs)/denominator if denominator>1e-12 else 0
  if lag==1:strong_dependence=rho>.5
  if rho<=.1:break
  length=max(length,2*(lag+1))
 result['chunk_seconds']=2*length
 if len(values)<(8 if strong_dependence else 4)*length or any(len(r)<length+1 for r in runs):
  return {**result,'reason':'More continuous clean data needed to estimate temporal dependence'}
 # Strong monotonic change contradicts the local stationarity assumed by this bootstrap.
 for r in runs:
  if len(r)>=12:
   trend=abs(np.polyfit(np.arange(len(r)),r,1)[0])*(len(r)-1)
   if trend>2*np.std(r,ddof=1):return {**result,'reason':'Strong within-period drift; descriptive statistics only'}
 rng=np.random.default_rng(seed);samples=np.zeros(draws)
 for r in runs:
  chunks=np.lib.stride_tricks.sliding_window_view(r,length)
  indices=rng.integers(len(chunks),size=(draws,int(np.ceil(len(r)/length))))
  resampled=chunks[indices].reshape(draws,-1)[:,:len(r)]
  # Center bootstrap errors on their own expectation to remove moving-window edge bias.
  means=resampled.mean(axis=1);samples+=(means-means.mean())*len(r)/len(values)
 from analysis import t_critical
 effective=len(values)/length
 samples*=t_critical(max(1,int(effective)-1))/1.96*np.sqrt(effective/(effective-1))
 return {**result,'ready':True,'mean':float(values.mean()),'errors':samples}

def compare_periods(left,right):
 a=bootstrap_periods(left,seed=1729);b=bootstrap_periods(right,seed=2903)
 base=dict(method='moving-block bootstrap',test='Exploratory within-recording comparison; conditional on sampled periods',seconds=[a['seconds'],b['seconds']])
 if not a['ready'] or not b['ready']:return {**base,'ready':False,'reason':'; '.join(f'Condition {i+1}: {v["reason"]}' for i,v in enumerate([a,b]) if not v['ready'])}
 difference=a['mean']-b['mean'];errors=a['errors']-b['errors']
 if np.std(errors)<1e-10:return {**base,'ready':False,'reason':'Too little resampling variation to estimate uncertainty'}
 p=float((1+np.count_nonzero(np.abs(errors)>=abs(difference)))/(len(errors)+1))
 lo,hi=np.quantile(errors,[.025,.975])
 return {**base,'ready':True,'difference':difference,'ci95':[float(difference-hi),float(difference-lo)],'p':p,'label':'***' if p<.001 else '**' if p<.01 else '*' if p<.05 else 'NS','chunk_seconds':[a['chunk_seconds'],b['chunk_seconds']],'resamples':len(errors)}
