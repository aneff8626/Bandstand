import unittest
import numpy as np
from analysis import FS,DEFAULT_THRESHOLDS,Filters
from tf_analysis import channel_windows,summarize_tf
class TFChannelTests(unittest.TestCase):
 def signals(self):
  t=np.arange(-2,12+1/FS,1/FS);x=np.tile((10*np.sin(2*np.pi*10*t))[:,None],(1,4));return t,x
 def test_missing_channel_does_not_reject_others(self):
  t,x=self.signals();x[:,0]=np.nan;y=Filters(notch_only=True).process(x)
  self.assertTrue(np.isfinite(y[:,1:]).all())
  r=channel_windows(x,y,t,[2,12],DEFAULT_THRESHOLDS)
  self.assertFalse(r['TP9']['accepted']);self.assertTrue(all(r[c]['accepted'] for c in ['AF7','AF8','TP10']))
 def test_local_artifact_preserves_clean_seconds_and_band_review(self):
  t,x=self.signals();x[(t>4)&(t<4.5),0]=1000
  r=channel_windows(x,x,t,[2,12],DEFAULT_THRESHOLDS)
  self.assertTrue(r['TP9']['accepted']);self.assertLess(r['TP9']['clean_seconds'],r['TP10']['clean_seconds'])
  trials=[dict(index=0,condition_index=0,spectral_channels=r)]
  s=dict(conditions=['Open','Closed'],minimum=10)
  alpha=summarize_tf(trials,s,[8,13]);beta=summarize_tf(trials,s,[20,30])
  self.assertGreater(alpha['channels']['TP10']['groups'][0]['mean'],beta['channels']['TP10']['groups'][0]['mean']+20)
  self.assertEqual(alpha['channels']['TP10']['groups'][0]['accepted'],1)
  self.assertFalse(alpha['channels']['TP10']['stats']['ready'])
 def test_less_than_four_seconds_is_not_a_block(self):
  t,x=self.signals();r=channel_windows(x,x,t,[2,5],DEFAULT_THRESHOLDS)
  self.assertFalse(r['TP10']['accepted'])
  a=summarize_tf([dict(index=0,condition_index=0,spectral_channels=r)],dict(conditions=['Open','Closed'],minimum=10),[8,13])
  g=a['channels']['TP10']['groups'][0]
  self.assertEqual(g['accepted'],0);self.assertEqual(len(g['segment_features']),1)

 def test_ten_blocks_each_and_multiple_conditions(self):
  trials=[]
  for condition in range(3):
   for n in range(10):
    rng=np.random.default_rng(condition*100+n);windows=[dict(start=2+2*k,end=4+2*k,power=[float(np.exp(rng.normal(condition,.2)))]*77,reasons=[]) for k in range(5)];row=dict(accepted=True,clean_seconds=10,psd=np.mean([w['power'] for w in windows],axis=0).tolist(),windows=windows)
    trials.append(dict(index=len(trials),condition_index=condition,spectral_channels={ch:row for ch in ['TP9','AF7','AF8','TP10']}))
  result=summarize_tf(trials,dict(conditions=['A','B','C'],minimum=10),[8.15,12.75])
  for channel in result['channels'].values():
   self.assertEqual(len(channel['pairwise']),3)
   self.assertTrue(all(p['ready'] and p['adjusted_p']>=p['p'] for p in channel['pairwise']))
  result=summarize_tf(trials[:20],dict(conditions=['A','B'],minimum=10),[8.15,12.75])
  self.assertTrue(all(c['stats']['ready'] for c in result['channels'].values()))
