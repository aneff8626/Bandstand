import unittest
import numpy as np
from point_statistics import adjust_pvalues,point_statistics
class PointStatisticsTests(unittest.TestCase):
 def test_known_corrections_and_order(self):
  p=[.04,.001,.03,.2]
  np.testing.assert_allclose(adjust_pvalues(p,'holm'),[.09,.004,.09,.2])
  np.testing.assert_allclose(adjust_pvalues(p,'bh'),[.053333333333,.004,.053333333333,.2])
  np.testing.assert_allclose(adjust_pvalues(p,'by'),np.minimum(1,np.array(adjust_pvalues(p,'bh'))*sum(1/i for i in range(1,5))))
  self.assertEqual(adjust_pvalues(p,'none'),p)
 def erp(self):
  rng=np.random.default_rng(19);trials=[]
  for ci in range(2):
   for i in range(25):
    trials.append(dict(index=len(trials),condition_index=ci,times=[0,.1,.2],channel_trials={'AF7':dict(accepted=True,wave=(rng.normal(0,.3,3)+[0,ci*3,0]).tolist()),'AF8':dict(accepted=False,wave=[0,0,0])}))
  return trials,dict(mode='erp',conditions=['A','B'],channels=['AF7','AF8'])
 def test_erp_all_trials_local_rejection_and_full_family(self):
  trials,s=self.erp();r=point_statistics(trials,s,0,200)
  self.assertEqual(r['family_size'],6);self.assertEqual(r['ready_count'],3)
  p=r['channels']['AF7']['points'][1];self.assertTrue(p['significant']);self.assertEqual(p['n'],[25,25]);self.assertLess(p['difference'],-2)
  self.assertFalse(r['channels']['AF8']['points'][1]['ready'])
 def test_single_sample_and_validation(self):
  trials,s=self.erp();r=point_statistics(trials,s,94,94,single=True)
  self.assertEqual(r['family_size'],2);self.assertEqual(r['channels']['AF7']['points'][0]['x'],100)
  for kwargs in [dict(low=1,high=2),dict(low=0,high=900),dict(low=0,high=200,first=1,second=1),dict(low=0,high=200,correction='oops')]:
   with self.assertRaises(ValueError):point_statistics(trials,s,**kwargs)
 def test_spectral_no_overlapping_window_inflation(self):
  rng=np.random.default_rng(5);trials=[]
  for ci in range(2):
   for b in range(4):
    windows=[]
    for k in range(17):windows.append(dict(start=k*.5,end=k*.5+2,power=np.exp(rng.normal(ci,.2,77)).tolist()))
    trials.append(dict(index=len(trials),condition_index=ci,spectral_channels={'AF7':dict(windows=windows)}))
  r=point_statistics(trials,dict(mode='tf',conditions=['A','B']),8,9,correction='bh')
  self.assertEqual(r['family_size'],12)
  for p in r['channels']['AF7']['points']:self.assertEqual(p['n'],[20,20])
  self.assertTrue(any(p['ready'] for p in r['channels']['AF7']['points']))
 def test_empty_and_speller_phase(self):
  trials,s=self.erp();s['protocol']='speller'
  for t in trials:t['speller']={'phase':'inference'}
  r=point_statistics(trials,s,0,200);self.assertEqual(r['ready_count'],0)
  r=point_statistics([],s,0,200);self.assertEqual(r['family_size'],0)
 def test_full_family_range_does_not_change_correction(self):
  trials,s=self.erp();full=point_statistics(trials,s,0,200,full_family=True);single=point_statistics(trials,s,100,100,single=True,full_family=True)
  self.assertEqual(full['family_size'],single['family_size'])
  self.assertEqual(full['channels']['AF7']['points'][1]['adjusted_p'],single['channels']['AF7']['points'][0]['adjusted_p'])
 def test_time_frequency_cell_counts_blocks_not_windows(self):
  from point_statistics import time_frequency_statistics
  rng=np.random.default_rng(88);trials=[]
  for ci in range(2):
   for b in range(5):
    windows=[dict(start=k*.5,end=k*.5+2,power=np.exp(rng.normal(ci*5,.2,77)).tolist()) for k in range(3)]
    trials.append(dict(condition_index=ci,spectral_channels={'AF7':dict(windows=windows+windows[:1])}))
  r=time_frequency_statistics(trials,dict(mode='tf',conditions=['A','B']))
  self.assertEqual(r['family_size'],4*3*77)
  self.assertTrue(all(p['n']==[5,5] for p in r['channels']['AF7']['points']))
  self.assertTrue(all(p['significant'] for p in r['channels']['AF7']['points']))
  self.assertTrue(all(not p['ready'] for p in r['channels']['TP9']['points']))
