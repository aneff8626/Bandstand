import time, unittest
import numpy as np
from test_analysis import Engine, FS

class LiveArtifactTests(unittest.TestCase):
    def test_current_artifact_clears_without_history_latch(self):
        e=Engine(); t=np.arange(FS)/FS
        clean=np.tile((20*np.sin(2*np.pi*10*t))[:,None],(1,4))
        e.raw.extend(clean.tolist()); e.times.extend((time.time()-1+t).tolist())
        self.assertEqual(e.live_artifacts(),[])
        e.raw[-1]=[1000]*4
        self.assertIn('signal clipping',e.live_artifacts())
        e.raw.extend(clean[:FS//2].tolist())
        e.times.extend((time.time()-.5+t[:FS//2]).tolist())
        self.assertEqual(e.live_artifacts(),[])
    def test_stale_signal_clears_indicator(self):
        e=Engine(); e.raw.extend([[1000]*4]*FS); e.times.extend([time.time()-3]*FS)
        self.assertEqual(e.live_artifacts(),[])

class MotionTests(unittest.TestCase):
    def test_stationary_gravity_is_not_movement(self):
        e=Engine()
        for _ in range(3): e.ingest_motion({'sensor':'acc','received':time.time(),'values':[[0,0,1]]*3})
        self.assertTrue(e.motion_state()['available'])
        self.assertFalse(e.motion_state()['moving'])
    def test_rotation_and_stale_sensor(self):
        e=Engine()
        for _ in range(3): e.ingest_motion({'sensor':'gyro','received':time.time(),'values':[[0,20,0]]*3})
        self.assertTrue(e.motion_state()['moving'])
        e.motion_samples['gyro'].clear()
        e.ingest_motion({'sensor':'gyro','received':time.time()-2,'values':[[0,20,0]]*3})
        self.assertFalse(e.motion_state()['moving'])
    def test_large_eeg_is_not_called_head_movement(self):
        from analysis import artifacts
        t=np.arange(FS)/FS
        x=np.tile((100*np.sin(2*np.pi*4*t))[:,None],(1,4))
        reasons=artifacts(x)
        self.assertIn('large EEG transient / possible contact noise',reasons)
        self.assertFalse(any('movement' in reason for reason in reasons))

class ArtifactRegionTests(unittest.TestCase):
    def test_region_tracks_data_clock_and_stops_growing(self):
        e=Engine(); e.times.extend([100,100.5]); e.update_artifact_regions(['probable blink'])
        self.assertEqual(e.artifact_regions[0]['onset'],100)
        e.times.append(100.75); e.update_artifact_regions(['probable blink'])
        self.assertEqual(len(e.artifact_regions),1)
        self.assertEqual(e.artifact_regions[0]['offset'],100.75)
        e.times.append(101); e.update_artifact_regions([])
        self.assertFalse(e.artifact_regions[0]['active'])
        self.assertEqual(e.artifact_regions[0]['offset'],100.75)
        e.times.append(102); e.update_artifact_regions(['probable blink'])
        self.assertEqual(len(e.artifact_regions),2)
    def test_regions_expire_and_source_switch_clears(self):
        e=Engine(); e.times.extend([100,100.5]); e.update_artifact_regions(['probable blink'])
        e.times.append(112); e.update_artifact_regions([])
        self.assertEqual(len(e.artifact_regions),0)
        e.update_artifact_regions(['probable blink']); e.switch_source('simulation')
        self.assertEqual(len(e.artifact_regions),0)


def setUpModule():
 import tempfile
 from pathlib import Path
 from unittest.mock import patch
 global _private_tmp,_private_patch
 _private_tmp=tempfile.TemporaryDirectory()
 _private_patch=patch('engine.DATA_ROOT',Path(_private_tmp.name)/'data');_private_patch.start()

def tearDownModule():
 _private_patch.stop();_private_tmp.cleanup()
