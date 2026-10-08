import unittest
import numpy as np
from calibrated_artifacts import classify

PROFILE={'rules':{'jaw_af7_ptp':160,'jaw_hf':.14,'blink_temporal_ptp':250,'blink_temporal_corr':.94,'saccade_corr':-.55,'head_rotation_dps':20},'rest_ptp_median':[70,45,30,70]}
class PersonalRuleTests(unittest.TestCase):
 def setUp(self):self.t=np.arange(128)/256;self.x=np.zeros((128,4))
 def test_temporal_blink_pattern(self):
  pulse=350*np.exp(-((self.t-.23)/.05)**2);self.x[:,0]=pulse;self.x[:,3]=pulse*.95;self.x[:,1]=pulse*.15;self.x[:,2]=-pulse*.05
  events=classify(self.x,self.t,PROFILE)
  self.assertEqual(events[0]['label'],'Blink');self.assertTrue(events[0]['uncertain'])
 def test_muscle_priority(self):
  self.x[:]=100*np.sin(2*np.pi*35*self.t)[:,None]
  events=classify(self.x,self.t,PROFILE)
  self.assertEqual([e['label'] for e in events],['Jaw clench / facial tension'])
 def test_clipping_abstains(self):
  self.x[40,0]=1000;self.assertEqual(classify(self.x,self.t,PROFILE),[])
 def test_head_motion_requires_sensor_and_signal_change(self):
  self.x[:]=80*np.sin(2*np.pi*7*self.t)[:,None]
  self.assertFalse(any(e['label']=='Head rotation' for e in classify(self.x,self.t,PROFILE)))
  self.assertTrue(any(e['label']=='Head rotation' for e in classify(self.x,self.t,PROFILE,{'gyro':40})))

