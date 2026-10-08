import io, json, math, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import *
from engine import Engine, PacketAssembler

class AnalysisTests(unittest.TestCase):
    def test_t_distribution_known_values(self):
        self.assertAlmostEqual(t_p(0,10),1,12)
        self.assertAlmostEqual(t_p(1,1),.5,10)
        self.assertAlmostEqual(t_p(2.2281388519649385,10),.05,10)
        self.assertAlmostEqual(t_critical(9),2.2621571628540993,8)
    def test_welch_and_minimum(self):
        self.assertFalse(compare(range(9),range(10))['ready'])
        self.assertFalse(compare([1]*10,[1]*10)['ready'])
        self.assertAlmostEqual(compare(range(10),range(10))['p'],1,10)
        result=compare(np.arange(10),np.arange(10)+5)
        self.assertAlmostEqual(result['df'],18,10)
        self.assertAlmostEqual(result['t'],-3.692744729379982,8)
    def test_notch_and_dc(self):
        t=np.arange(FS*20)/FS
        sine=lambda f:np.repeat((20*np.sin(2*np.pi*f*t)+200)[:,None],4,axis=1)
        notch=Filters().process(sine(60))[FS*10:]
        alpha=Filters().process(sine(10))[FS*10:]
        self.assertLess(np.std(notch),np.std(alpha)*.01)
        self.assertLess(abs(np.mean(alpha)),1)
    def test_filter_gap_reset(self):
        x=np.ones((1000,4))*300;x[500]=np.nan
        y=Filters().process(x)
        self.assertTrue(np.isnan(y[500]).all());self.assertTrue(np.isfinite(y[501:]).all())
        self.assertLess(np.max(abs(y[501:])),1e-7)
    def test_artifact_labels(self):
        rng=np.random.default_rng(9); x=rng.normal(0,3,(FS*2,4))
        self.assertEqual(artifacts(x),[])
        flat=x.copy();flat[:,0]=0;self.assertTrue(any('flat' in r for r in artifacts(flat)))
        blink=x.copy();blink[100:120,1]+=200;self.assertIn('probable blink',artifacts(blink))
        clip=x.copy();clip[20,3]=1000;self.assertIn('signal clipping',artifacts(clip))
        missing=x.copy();missing[20,0]=np.nan;self.assertTrue(any('data loss' in r for r in artifacts(missing)))
        muscle=x+40*np.sin(2*np.pi*35*np.arange(FS*2)/FS)[:,None];self.assertIn('probable muscle artifact',artifacts(muscle))
    def test_spectrum_units_and_frequency(self):
        t=np.arange(FS*4)/FS;x=(10*np.sin(2*np.pi*10*t))[:,None]
        self.assertAlmostEqual(float(bandpower(x)[0]),50,delta=.1)
        tf=time_frequency(x[:,0],t);self.assertEqual(tf['frequencies'][np.argmax(np.mean(tf['power_db'],1))],10)
    def test_packet_wrap_missing_and_no_channel_mixing(self):
        output=[];a=PacketAssembler(lambda ts,x:output.append((ts,x)))
        for c in [65535,0,2]:
            for ch in CHANNELS:a.add(dict(counter=c,received=100+len(output)*.1,channel=ch,values=[CHANNELS.index(ch)]*12))
        self.assertEqual(a.missing,12);self.assertEqual(len(output),3)
        self.assertTrue(np.all(np.diff(np.concatenate([o[0] for o in output]))>0))
        self.assertTrue(np.all(output[0][1][:,3]==3))
        a.add(dict(counter=3,received=101,channel='TP9',values=[9]*12));a.add(dict(counter=4,received=101.3,channel='AF7',values=[8]*12))
        self.assertTrue(np.isnan(output[-1][1][:,1:]).all())
    def test_ci_starts_at_ten(self):
        self.assertIsNone(summarize(np.ones((9,4)))['ci95'])
        self.assertIsNotNone(summarize(np.ones((10,4)))['ci95'])

class PipelineTests(unittest.TestCase):
    def test_session_exports_baseline_and_rejection(self):
        with tempfile.TemporaryDirectory() as tmp, patch('engine.ROOT',Path(tmp)),patch('engine.DATA_ROOT',Path(tmp)/'data'):
            (Path(tmp)/'data').mkdir();(Path(tmp)/'stimuli').mkdir()
            clock=[1700000000.]
            with patch('engine.time.time',lambda:clock[0]):
                e=Engine();e.source='simulation';rng=np.random.default_rng(5)
                cursor=clock[0]-4
                def feed(seconds,effect=None):
                    nonlocal cursor
                    t=cursor+np.arange(1,round(seconds*FS)+1)/FS;cursor=t[-1];clock[0]=cursor
                    x=rng.normal(0,3,(len(t),4))+5*np.sin(2*np.pi*10*t[:,None])
                    if effect is not None:x+=effect(t)
                    e.ingest(t,x)
                feed(4)
                session=e.begin({'protocol':'oddball','trials':40,'channels':['TP9','TP10']})
                for i in range(22):
                    feed(.4);onset=cursor
                    e.event({'kind':'stimulus','index':i,'condition_index':i%2,'onset':onset})
                    if i==21: feed(1.,lambda t:np.where((t[:,None]-onset<.3)&(t[:,None]-onset>.2),220.,0.))
                    else: feed(1.,lambda t:(4+6*(i%2))*np.exp(-((t[:,None]-onset-.4)/.07)**2))
                e.stop();a=e.analysis()
                self.assertEqual(len(e.trials),22);self.assertEqual(sum(t['accepted'] for t in e.trials),21)
                self.assertTrue(a['stats']['ready']);self.assertLess(a['stats']['p'],.001)
                for t in e.trials:
                    if t['accepted']: self.assertLess(abs(np.mean(np.array(t['wave'])[np.array(t['times'])<0])),.2)
                for kind in ['raw','processed']:
                    data,_,_=e.export(kind);z=zipfile.ZipFile(io.BytesIO(data));self.assertIn('session.json',z.namelist())
                    if kind=='raw':self.assertIn('continuous.csv',z.namelist());self.assertIn('events.json',z.namelist())
                    else:self.assertIn('trial-summary.csv',z.namelist());self.assertIn('erp-0.csv',z.namelist())
                data,_,_=e.export('pdf');self.assertTrue(data.startswith(b'%PDF'))
                dest=Path(__file__).resolve().parents[1]/'build/qa';dest.mkdir(parents=True,exist_ok=True);(dest/'example-report.pdf').write_bytes(data)
    def test_time_frequency_block_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp, patch('engine.ROOT',Path(tmp)),patch('engine.DATA_ROOT',Path(tmp)/'data'):
            (Path(tmp)/'data').mkdir(); (Path(tmp)/'stimuli').mkdir()
            clock=[1700000000.]
            with patch('engine.time.time',lambda:clock[0]):
                e=Engine();e.source='simulation';rng=np.random.default_rng(23)
                t=clock[0]-4+np.arange(FS*4)/FS
                x=rng.normal(0,3,(len(t),4))+8*np.sin(2*np.pi*10*t[:,None])
                e.ingest(t,x);e.begin({'protocol':'alpha','trials':20})
                onset=clock[0];e.event({'kind':'stimulus','index':0,'condition_index':0,'onset':onset})
                t=onset+np.arange(FS*9)/FS;clock[0]=t[-1]
                e.ingest(t,rng.normal(0,3,(len(t),4))+8*np.sin(2*np.pi*10*t[:,None]))
                e.stop();self.assertEqual(len(e.trials),1);self.assertTrue(e.trials[0]['accepted'])
                self.assertIsNotNone(e.trials[0]['tf']);self.assertAlmostEqual(e.trials[0]['feature'],32,delta=4)
                self.assertFalse(e.analysis()['stats']['ready'])

    def test_no_live_data_cannot_start(self):
        with tempfile.TemporaryDirectory() as tmp, patch('engine.ROOT',Path(tmp)),patch('engine.DATA_ROOT',Path(tmp)/'data'):
            e=Engine()
            with self.assertRaisesRegex(ValueError,'No recent EEG'):e.begin({'protocol':'oddball'})

if __name__=='__main__':unittest.main(verbosity=2)
