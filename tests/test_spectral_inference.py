import unittest
import numpy as np
from spectral_inference import compare_periods,bootstrap_periods
class SpectralInferenceTests(unittest.TestCase):
 def test_descriptive_wait_and_gaps(self):
  self.assertFalse(compare_periods([[1,2]],[[2,3]])['ready'])
  self.assertFalse(bootstrap_periods([[1,2]]*20)['ready'])
 def test_short_repeated_periods_and_shift(self):
  rng=np.random.default_rng(32)
  a=[rng.normal(size=5) for _ in range(5)];b=[rng.normal(4,1,size=5) for _ in range(5)]
  s=compare_periods(a,b);self.assertTrue(s['ready']);self.assertLess(s['ci95'][1],0);self.assertLess(s['p'],.05)
  self.assertEqual(s,compare_periods(a,b))
 def test_drift_and_flatline(self):
  self.assertFalse(bootstrap_periods([np.arange(40.)])['ready'])
  self.assertFalse(bootstrap_periods([np.ones(40)])['ready'])
 def test_autocorrelated_null_simulation(self):
  rng=np.random.default_rng(98622);false_positives=0
  for _ in range(100):
   runs=[]
   for condition in range(2):
    x=np.zeros(200)
    for i in range(1,len(x)):x[i]=.5*x[i-1]+rng.normal()
    runs.append([x[140:]])
   s=compare_periods(*runs)
   false_positives+=s['ready'] and s['p']<.05
  self.assertLessEqual(false_positives,12)
