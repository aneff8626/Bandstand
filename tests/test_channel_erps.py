import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from engine import Engine
from analysis import FS
class ChannelERPTests(unittest.TestCase):
 def test_noisy_tp9_retains_tp10(self):
  with tempfile.TemporaryDirectory() as tmp,patch('engine.ROOT',Path(tmp)),patch('engine.DATA_ROOT',Path(tmp)/'data'):
   e=Engine();rng=np.random.default_rng(91);onset=time.time();t=onset-4+np.arange(4*FS)/FS;e.ingest(t,rng.normal(0,3,(len(t),4)))
   e.begin({'protocol':'oddball','trials':20,'channels':['TP9','TP10']})
   e.event({'kind':'stimulus','index':0,'condition_index':1,'onset':onset})
   t=onset+np.arange(FS+20)/FS;x=rng.normal(0,3,(len(t),4));x[40:60,0]+=400;e.ingest(t,x);e.process_pending()
   trial=e.trials[0];self.assertFalse(trial['accepted']);self.assertFalse(trial['channel_trials']['TP9']['accepted']);self.assertTrue(trial['channel_trials']['TP10']['accepted'])
   a=e.analysis();self.assertEqual(a['channels']['TP10']['groups'][1]['accepted'],1);self.assertEqual(a['channels']['TP9']['groups'][1]['rejected'],1);e.stop()
