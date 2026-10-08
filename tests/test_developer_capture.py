import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from developer_capture import DeveloperCapture
from analysis import FS

class DeveloperTests(unittest.TestCase):
 def test_labeled_capture_saves_raw_and_comparison(self):
  with tempfile.TemporaryDirectory() as d:
   capture=DeveloperCapture(d)
   with patch('developer_capture.time.time',return_value=100):capture.start('blink','live')
   t=100+np.arange(28*FS)/FS
   x=np.tile(np.sin(np.arange(len(t))/4)[:,None],(1,4));x[t>=108]*=3
   capture.add(t,x,x)
   with patch('developer_capture.time.time',return_value=129):status=capture.status()
   self.assertFalse(status['recording']);report=status['last']
   self.assertTrue(report['action']['usable']);self.assertTrue(report['rest']['usable'])
   self.assertAlmostEqual(report['std_ratio_action_to_rest'][0],3,delta=.03)
   self.assertTrue(Path(report['file']).exists())
   data=np.load(report['file'].replace('.json','.npz'));self.assertEqual(data['raw'].shape,(28*FS,4))
 def test_partial_and_gaps_are_not_valid_examples(self):
  with tempfile.TemporaryDirectory() as d:
   c=DeveloperCapture(d);c.start('jaw_clench','live');result=c.finish(cancel=True)
   self.assertTrue(result['cancelled']);self.assertFalse(result['action']['usable'])
 def test_source_and_concurrent_recording_guards(self):
  with tempfile.TemporaryDirectory() as d:
   c=DeveloperCapture(d)
   with self.assertRaises(ValueError):c.start('blink','simulation')
   with self.assertRaises(ValueError):c.start('blink','live',True)

class CueTests(unittest.TestCase):
 def test_cadence_and_blink_count(self):
  from developer_capture import cue_plan
  for action in ['look_up_down','saccade','blink','jaw_clench','tongue_movement','head_rotation']:
   cues=cue_plan(action,108)
   self.assertEqual(len(cues),20)
   self.assertEqual([c['onset'] for c in cues],list(range(108,128)))
  self.assertEqual([c['target'] for c in cue_plan('look_up_down',0)][:4],['up','down','up','down'])
  self.assertEqual([c['target'] for c in cue_plan('saccade',0)][:4],['left','right','left','right'])
  self.assertEqual(sum(c['label'].startswith('Blink ') for c in cue_plan('blink',0)),10)
 def test_observed_cues_are_saved_once(self):
  with tempfile.TemporaryDirectory() as d:
   c=DeveloperCapture(d);c.start('blink','live')
   body={'capture_id':c.current['id'],'index':0,'displayed_at':c.current['action_onset']+.02}
   c.cue(body);c.cue(body)
   report=c.finish(cancel=True)
   self.assertEqual(len(report['displayed_cues']),1)
   self.assertEqual(report['requested_action'],'blink')

 def test_free_recording_starts_immediately_and_saves_manual_duration(self):
  with tempfile.TemporaryDirectory() as d:
   c=DeveloperCapture(d)
   with patch('developer_capture.time.time',return_value=100):c.start('free_recording','live')
   self.assertEqual(c.current['action_onset'],100)
   self.assertEqual(c.current['cues'],[])
   t=100+np.arange(2*FS)/FS;x=np.tile(np.sin(np.arange(len(t))/4)[:,None],(1,4));c.add(t,x,x)
   with patch('developer_capture.time.time',return_value=102):report=c.finish()
   self.assertEqual(report['ends'],102);self.assertFalse(report['cancelled'])
   self.assertEqual(report['requested_action'],'free_recording')
   self.assertFalse(report['rest']['usable']);self.assertTrue(report['action']['usable'])
   self.assertEqual(np.load(report['file'].replace('.json','.npz'))['raw'].shape,(512,4))
