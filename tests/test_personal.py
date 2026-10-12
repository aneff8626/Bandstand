import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from personal import PersonalActivities,questionnaire,score
from analysis import FS
class PersonalTests(unittest.TestCase):
 def test_scores(self):
  self.assertEqual(score('extraversion',[5]*5+[1]*5)['Extraversion'],5)
  self.assertEqual(score('extraversion',[1]*5+[5]*5)['Extraversion'],1)
  self.assertEqual(len(questionnaire('big5')),50)
  self.assertTrue(all(v==3 for v in score('big5',[3]*50).values()))
  for answers in [[],[True]*10,[6]*10]:
   with self.assertRaises(ValueError):score('extraversion',answers)
 def test_consent_and_local_persistence(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=PersonalActivities(tmp);self.assertFalse(p.connected()['enabled'])
   with self.assertRaises(ValueError):p.request('preferences',{},None)
   p.request('preferences',{'version':'personal-v1','personalize':True},None)
   p.write(p.root/'record-test.json',{'kind':'extraversion','scores':score('extraversion',[3]*10)})
   self.assertEqual(p.connected()['questionnaires'],1)
   p.request('preferences',{'version':'personal-v1','personalize':False},None)
   self.assertEqual(p.connected(),{'enabled':False});self.assertEqual(len(p.history()),1)
 def test_reset_pipeline_missing_channel_and_recovery(self):
  with tempfile.TemporaryDirectory() as tmp,patch('personal.time.time',return_value=1000):
   p=PersonalActivities(tmp);e=SimpleNamespace(times=[1000],typing=SimpleNamespace(running=False),developer=SimpleNamespace(current=None),session=None,source='simulation')
   p.request('start',{'kind':'reset'},e)
   rng=np.random.default_rng(12)
   for second in range(2,226,2):
    t=1000+second-2+np.arange(FS*2)/FS
    x=rng.normal(0,2,(len(t),4))+8*np.sin(2*np.pi*10*t[:,None]);x[:,0]=np.nan
    p.ingest(t,x,x)
   p.finish('test completed') if p.current else None
   h=p.history()[0];self.assertEqual(len(h['summary']['ranking']),3)
   self.assertTrue(all(r['channels']==3 for r in h['summary']['ranking']))
   p.request('start',{'kind':'eeg_profile'},e)
   t=1002+np.arange(FS*2)/FS;x=rng.normal(0,2,(len(t),4));p.ingest(t,x,x)
   recovered=PersonalActivities(tmp);self.assertFalse(recovered.status()['running']);self.assertIn('Interrupted',[r['reason'].split()[0] for r in recovered.history()])
 def test_questionnaire_records_eeg_and_events(self):
  import gzip,json
  with tempfile.TemporaryDirectory() as tmp,patch('personal.time.time',return_value=1000):
   p=PersonalActivities(tmp);e=SimpleNamespace(times=[],typing=SimpleNamespace(running=False),developer=SimpleNamespace(current=None),session=None,source='simulation')
   with self.assertRaises(ValueError):p.request('start',{'kind':'extraversion'},e)
   e.times=[1000];p.request('start',{'kind':'extraversion'},e)
   p.record_raw([1000],[[1,2,3,4]])
   p.request('questionnaire-event',{'index':0,'value':3},e)
   r=p.request('questionnaire',{'kind':'extraversion','answers':[3]*10},e)
   self.assertFalse(p.current);self.assertEqual(r['scores']['Extraversion'],3)
   self.assertEqual(r['answer_events'][0]['time'],1000)
   with gzip.open(p.root/r['raw_eeg_file'],'rt') as f:self.assertEqual(json.loads(f.readline())['uv'],[1,2,3,4])
   with self.assertRaises(ValueError):p.request('questionnaire',{'kind':'extraversion','answers':[3]*10},e)
 def test_social_hypothesis_requires_both_channels(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=PersonalActivities(tmp)
   phases={'Browse messages':{},'Send a message':{}}
   for ch in ('AF7','AF8'):
    phases['Browse messages'][ch]={'n':12,'db':[0,0,0,0]}
    phases['Send a message'][ch]={'n':12,'db':[2,0,0,0]}
   self.assertIn('more mental effort',p.hypothesis(phases,'social_probe')['text'])
   phases['Send a message']['AF8']['n']=0
   self.assertIn('Not enough',p.hypothesis(phases,'social_probe')['text'])
 def test_signal_loss(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=PersonalActivities(tmp);p.current={'plan':[],'clips':[],'kind':'reset','id':'test','created':0};p.last_sample=0
   self.assertFalse(p.status()['running']);self.assertEqual(p.history()[0]['reason'],'Signal lost; partial recording saved')
if __name__=='__main__':unittest.main()
