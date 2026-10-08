import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from typing_lab import TypingLab,eeg_features,evaluate,fit_ridge,predict,word_label
from analysis import FS

class TypingTests(unittest.TestCase):
 def data(self):
  t=98+np.arange(5*FS)/FS;rng=np.random.default_rng(4);x=rng.normal(0,2,(len(t),4))+4*np.sin(2*np.pi*10*t[:,None]+np.arange(4));return t,x
 def test_features_and_shapes(self):
  _,x=self.data();f=eeg_features(x[:256]);self.assertEqual(f.shape,(118,));self.assertTrue(np.isfinite(f).all())
  with self.assertRaises(ValueError):eeg_features(x[:20])
 def test_words_and_typo_labels(self):
  self.assertEqual(word_label('Teh,'),'teh');self.assertEqual(word_label('Hello!'),'hello');self.assertEqual(word_label('...'),'')
 def test_collect_epoch_and_restart_dataset(self):
  with tempfile.TemporaryDirectory() as root:
   lab=TypingLab(root);t,x=self.data()
   with patch('typing_lab.time.time',return_value=99):lab.start()
   lab.ingest(t,x,x)
   with patch('typing_lab.time.time',return_value=100):
    lab.event({'kind':'onset','id':'word-1','onset':100},t[t<100],x[t<100],x[t<100])
    lab.event({'kind':'edit','onset':100.1},t[t<100.1],x[t<100.1],x[t<100.1])
    lab.event({'kind':'commit','id':'word-1','onset':100.8,'text':'hello','edited':True},t,x,x)
   self.assertEqual(lab.rows[0]['label'],'hello');self.assertTrue(lab.rows[0]['edited']);self.assertTrue(lab.rows[0]['accepted']['pre']);self.assertTrue(lab.rows[0]['accepted']['post'])
   self.assertTrue((lab.directory/'word-1.npz').exists());lab.stop();again=TypingLab(root);self.assertEqual(again.status()['counts'],{'hello':1})
 def test_previous_typing_is_retained_as_context(self):
  with tempfile.TemporaryDirectory() as root:
   lab=TypingLab(root);t,x=self.data()
   with patch('typing_lab.time.time',return_value=99):lab.start()
   with patch('typing_lab.time.time',return_value=100):
    lab.event({'kind':'edit','onset':99.5},[],[],[])
    lab.event({'kind':'onset','id':'second','onset':100},t,x,x)
   self.assertTrue(lab.pending['second']['accepted']['pre']);self.assertTrue(lab.pending['second']['overlapping_typing']);lab.stop()
 def test_artifact_and_invalid_identifier(self):
  with tempfile.TemporaryDirectory() as root:
   lab=TypingLab(root);t,x=self.data();x[(t>99)&(t<100),0]=1000
   with patch('typing_lab.time.time',return_value=99):lab.start()
   with patch('typing_lab.time.time',return_value=100):
    with self.assertRaises(ValueError):lab.event({'kind':'onset','id':'../escape','onset':100},t,x,x)
    lab.event({'kind':'onset','id':'clip','onset':100},t,x,x)
   self.assertTrue(lab.pending['clip']['accepted']['pre']);self.assertNotIn('TP9',lab.pending['clip']['channel_quality']['pre']['usable_channels']);self.assertIsNone(lab.prediction['word']);lab.stop()
 def test_no_predictions_before_evidence(self):
  model,report=evaluate([], 'pre',1);self.assertIsNone(model);self.assertFalse(report['ready'])
 def test_later_blocks_and_real_signal_gate(self):
  rng=np.random.default_rng(99);rows=[]
  for block in range(24):
   for k in range(12):
    label='apple' if k%2 else 'stone';signal=(1 if label=='apple' else -1)
    rows.append(dict(onset=block*60+k*4,block=str(block),label=label,accepted={'pre':True},features={'pre':(rng.normal(0,.1,12)+signal).tolist()}))
  model,report=evaluate(rows,'pre',1)
  self.assertTrue(report['ready']);self.assertIsNotNone(model);self.assertEqual(report['accuracy'],1.)
  # Same model shape receives no text or keystroke predictors.
  self.assertEqual(predict(model,np.ones(12))[0],'apple')
  for r in rows:r['features']['pre']=rng.normal(size=12).tolist()
  model,report=evaluate(rows,'pre',1);self.assertFalse(report['ready']);self.assertIsNone(model)
 def test_training_normalization_ignores_future_blocks(self):
  # Scaling and class targets come only from the explicitly supplied training matrix.
  x=np.array([[-1,0],[-2,1],[1,0],[2,1]],float);m=fit_ridge(x,['a','a','b','b'],['a','b'])
  np.testing.assert_allclose(m['mean'],[0,.5])
 def test_next_word_overlap_is_retained(self):
  with tempfile.TemporaryDirectory() as root:
   lab=TypingLab(root);t,x=self.data()
   with patch('typing_lab.time.time',return_value=99):lab.start('post')
   with patch('typing_lab.time.time',return_value=100):
    lab.event({'kind':'onset','id':'one','onset':100},t[t<100],x[t<100],x[t<100])
    lab.event({'kind':'onset','id':'two','onset':100.5},t,x,x)
   self.assertTrue(lab.pending['one']['accepted']['post']);self.assertTrue(lab.pending['one']['overlapping_typing']);lab.stop()
 def test_engine_live_and_concurrent_recording_guards(self):
  from engine import Engine
  with tempfile.TemporaryDirectory() as root,patch('engine.ROOT',Path(root)):
   e=Engine()
   with self.assertRaises(ValueError):e.typing_request('typing/start',{})
   t,x=self.data();e.times.extend(t);e.raw.extend(x.tolist());e.filtered.extend(x.tolist())
   with patch('engine.time.time',return_value=102.9):e.typing_request('typing/start',{})
   with self.assertRaises(ValueError):e.switch_source('simulation')
   with self.assertRaises(ValueError):e.begin({})
   e.typing_request('typing/stop',{})
