import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from engine import Engine
from analysis import FS
class PreflightTests(unittest.TestCase):
 def test_override_only_bypasses_contact_gate(self):
  with tempfile.TemporaryDirectory() as tmp, patch('engine.ROOT',Path(tmp)),patch('engine.DATA_ROOT',Path(tmp)/'data'):
   e=Engine(); now=time.time();t=now-4+np.arange(4*FS)/FS
   e.ingest(t,np.zeros((len(t),4)))
   cfg={'protocol':'oddball','trials':20}
   with self.assertRaisesRegex(ValueError,'Improve contact'):e.begin(cfg)
   session=e.begin({**cfg,'allow_noisy_start':True})
   self.assertTrue(session['preflight_quality']['continued_anyway'])
   self.assertTrue(session['preflight_quality']['warnings'])
   self.assertTrue(session['thresholds'])
   e.stop()
   e.times.clear()
   with self.assertRaisesRegex(ValueError,'No recent EEG'):e.begin({**cfg,'allow_noisy_start':True})
