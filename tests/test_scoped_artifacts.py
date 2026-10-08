import unittest
import numpy as np
from analysis import FS
from live_artifacts import detect_events, ocular_event

class ScopedArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.t=np.arange(FS//2)/FS
        self.clean=np.tile((10*np.sin(2*np.pi*10*self.t))[:,None],(1,4))
    def test_single_channel_noise_does_not_spread(self):
        x=self.clean.copy();x[50:55,0]=999
        events=detect_events(x,self.t)
        self.assertTrue(events)
        self.assertTrue(all(e['channels']==['TP9'] for e in events))
        self.assertEqual(events[0]['onset'],self.t[50])
        self.assertEqual(events[0]['offset'],self.t[54])
    def test_matched_pulse_is_probable_blink(self):
        x=self.clean.copy(); pulse=180*np.exp(-((self.t-.23)/.05)**2)
        x[:,1]=pulse; x[:,2]=pulse*.9
        event=ocular_event(x,self.t)
        self.assertEqual(event['label'],'probable blink')
        self.assertEqual(len(event['channels']),4)
    def test_opposed_step_is_possible_horizontal_saccade(self):
        x=self.clean.copy();step=160/(1+np.exp(-(self.t-.2)/.01))
        x[:,1]=step;x[:,2]=-step
        self.assertEqual(ocular_event(x,self.t)['label'],'possible horizontal saccade')
    def test_frontal_muscle_suppresses_eye_label(self):
        x=self.clean.copy();pulse=180*np.exp(-((self.t-.23)/.05)**2)
        muscle=150*np.sin(2*np.pi*35*self.t)
        x[:,1]=pulse+muscle;x[:,2]=pulse+muscle
        events=detect_events(x,self.t)
        self.assertTrue(any(e['label']=='Muscle tension' for e in events))
        self.assertFalse(any(e['kind']=='ocular' for e in events))
    def test_temporal_muscle_does_not_suppress_frontal_blink(self):
        x=self.clean.copy();pulse=180*np.exp(-((self.t-.23)/.05)**2)
        x[:,1]=pulse;x[:,2]=pulse;x[:,0]=150*np.sin(2*np.pi*35*self.t)
        events=detect_events(x,self.t)
        self.assertTrue(any(e['label']=='probable blink' for e in events))
        self.assertTrue(any(e['label']=='Muscle tension' for e in events))
