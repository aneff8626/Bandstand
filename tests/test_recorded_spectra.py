import tempfile
import unittest
import numpy as np
from personal import PersonalActivities

class RecordedSpectraTests(unittest.TestCase):
 def record(self,blocks=4):
  return dict(kind='enneagram',created=0,plan=[['Questionnaire',60]],clips=[dict(time=b*10+j*2+1,phase='Questionnaire',phase_start=0,power={'AF7':[1]*4},spectra={'AF7':[float(b+1)]*79}) for b in range(blocks) for j in range(5)])
 def test_channel_exclusion_and_interval(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=PersonalActivities(tmp);result=p.summarize(self.record())['spectra']['Questionnaire']['channels']
   self.assertIsNone(result[0]);c=result[1]
   self.assertEqual(c['ci_blocks'],4);self.assertEqual(c['n'],20)
   self.assertEqual(len(c['ci_low']),79)
   self.assertTrue(np.all(np.array(c['ci_low'])<=c['psd']))
   self.assertTrue(np.all(np.array(c['ci_high'])>=c['psd']))
   self.assertGreater(c['ci_high'][0]-c['psd'][0],1)
 def test_no_interval_for_insufficient_blocks(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=PersonalActivities(tmp).summarize(self.record(2))['spectra']['Questionnaire']['channels'][1]
   self.assertIsNone(c['ci_low']);self.assertIsNone(c['ci_high'])
 def test_old_cache_is_rebuilt(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=PersonalActivities(tmp);r=self.record();r['id']='abc';p.write(p.root/'record-abc.json',r)
   p.write(p.root/'spectral-abc.json',{'spectra':{}})
   result=p.request('spectral-results',{'id':'abc'},None)
   self.assertEqual(result['spectrum_version'],2)
   self.assertIsNotNone(result['spectra']['Questionnaire']['channels'][1]['ci_low'])
if __name__=='__main__':unittest.main()
