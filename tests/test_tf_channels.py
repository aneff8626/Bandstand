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
