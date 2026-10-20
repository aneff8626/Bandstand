import tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from personal import PersonalActivities,custom_band_db
import numpy as np

class FeedbackSettingsTests(unittest.TestCase):
 def test_configuration_and_independent_channels(self):
  with tempfile.TemporaryDirectory() as tmp,patch('personal.time.time',return_value=1000):
   p=PersonalActivities(tmp);e=SimpleNamespace(times=[1000],typing=SimpleNamespace(running=False),developer=SimpleNamespace(current=None),session=None,source='simulation')
   config={'band':2,'channels':['TP9'],'direction':-1}
   r=p.request('start',{'kind':'biofeedback','feedback':config},e)
   self.assertEqual(r['feedback'],config)
   p.current['clips']=[{'phase':'Baseline','phase_start':0,'power':{'TP9':[1,2,3,4]}},{'phase':'Baseline','phase_start':0,'power':{'TP9':[3,4,5,6]}}]
   summary=p.summarize(p.current)
   self.assertAlmostEqual(summary['phases']['Baseline']['TP9']['sd'][0],2**.5)
   self.assertEqual(summary['phases']['Baseline']['TP10']['n'],0)
   p.finish('test');self.assertEqual(p.history()[0]['feedback'],config)
   for bad in [{'band':99,'channels':['TP9'],'direction':1},{'band':1,'channels':[],'direction':1},{'band':1,'channels':['bad'],'direction':1}]:
    with self.assertRaises(ValueError):p.request('start',{'kind':'biofeedback','feedback':bad},e)
 def test_custom_frequency_limits(self):
  # Fractional frequency edges must contribute proportionately, not snap to bins.
  f=np.arange(0,41,.5);density=np.ones_like(f)*2
  self.assertAlmostEqual(custom_band_db(f,density,[8.15,12.35]),10*np.log10(8.4))
  with tempfile.TemporaryDirectory() as tmp,patch('personal.time.time',return_value=1000):
   p=PersonalActivities(tmp);e=SimpleNamespace(times=[1000],typing=SimpleNamespace(running=False),developer=SimpleNamespace(current=None),session=None,source='simulation')
   config={'band':4,'range':[8.15,12.35],'channels':['AF7'],'direction':1}
   r=p.request('start',{'kind':'biofeedback','feedback':config},e);self.assertEqual(r['feedback'],config);p.finish('test')
   for limits in [[12,8],[0,8],[8,41],[8,float('nan')],[8,8.01]]:
    with self.assertRaises(ValueError):p.request('start',{'kind':'biofeedback','feedback':{**config,'range':limits}},e)
 def test_history_spread_without_answers(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=PersonalActivities(tmp);p.write(p.root/'record-test.json',{'kind':'big5','answers':[1,3,5]+[None]*47})
   r=p.history()[0];self.assertEqual(r['survey_spread']['Extraversion'],2);self.assertNotIn('answers',r)
if __name__=='__main__':unittest.main()
