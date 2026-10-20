import unittest
import numpy as np
from live_spectrum import rolling_spectra

class SpectrumTests(unittest.TestCase):
    def test_sine_power_and_peak(self):
        t=np.arange(256*8)/256
        x=np.tile((10*np.sin(2*np.pi*10*t))[:,None],(1,4))
        result=rolling_spectra(t,x)['8']
        ch=result['channels'][0]
        self.assertEqual(result['frequencies'][np.argmax(ch['psd'])],10)
        self.assertAlmostEqual(ch['bands'][2],50,places=2)
        self.assertEqual(ch['segments'],7)
    def test_channel_gaps_do_not_remove_others(self):
        t=np.arange(256*4)/256;x=np.ones((len(t),4));x[:,0]=np.nan
        result=rolling_spectra(t,x)['4']['channels']
        self.assertIsNone(result[0]);self.assertIsNotNone(result[1])
    def test_insufficient_and_timestamp_gap(self):
        self.assertEqual(rolling_spectra([0],[[1]*4]),{})
        t=np.arange(512)/256;t[256:]+=1
        self.assertTrue(all(c is None for c in rolling_spectra(t,np.ones((512,4)))['4']['channels']))
