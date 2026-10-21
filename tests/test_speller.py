import unittest
import numpy as np
from speller import fit,decode,SYMBOLS

class SpellerTests(unittest.TestCase):
    def rows(self,seed=1):
        rng=np.random.default_rng(seed);rows=[]
        for group,target in enumerate([0,7,14,21,28,35,4,31]):
            for rep in range(5):
                for line in range(12):
                    attended=line in (target//6,6+target%6)
                    features={'TP10':rng.normal(0,.4,12)+np.array([0,0,0,1,2,3,3,2,1,0,0,0])*attended}
                    rows.append(dict(features=features,group=group,line=line,target=target,phase='calibration'))
        return rows
    def test_held_out_character_and_bad_channels(self):
        rows=self.rows()
        for group in range(8):
            train=[r for r in rows if r['group']!=group];test=[r for r in rows if r['group']==group]
            model=fit(train);self.assertEqual(list(model),['TP10'])
            self.assertEqual(decode(test,model)['index'],test[0]['target'])
    def test_prediction_does_not_read_target(self):
        rows=self.rows();model=fit(rows)
        test=[dict(r,target=None,phase='spelling') for r in rows if r['group']==3]
        self.assertEqual(decode(test,model)['index'],21)
    def test_missing_row_abstains(self):
        rows=self.rows();self.assertIsNone(decode([r for r in rows if r['line']!=5],fit(rows))['symbol'])
    def test_insufficient_training(self):
        self.assertEqual(fit(self.rows()[:12]),{})
    def test_null_model_abstains(self):
        self.assertIsNone(decode(self.rows(),{})['symbol'])
    def test_alphabet(self):
        self.assertEqual(len(SYMBOLS),36);self.assertEqual(len(set(SYMBOLS)),36)
if __name__=='__main__':unittest.main()

class SpellerIntegrationTests(unittest.TestCase):
    def test_examples_keeps_only_accepted_channels(self):
        from types import SimpleNamespace
        from speller import examples
        times=np.arange(-51,206)/256
        engine=SimpleNamespace(events=[dict(kind='stimulus',index=0,speller=dict(group=0,line=0,target=0,phase='calibration'))],trials=[dict(index=0,times=times,channel_trials={'TP9':dict(accepted=False,wave=None),'TP10':dict(accepted=True,wave=np.ones(len(times))*4)})])
        rows=examples(engine);self.assertEqual(list(rows[0]['features']),['TP10']);np.testing.assert_allclose(rows[0]['features']['TP10'],4)
    def test_reject_spelling_target_label(self):
        import threading,time
        from engine import Engine
        e=Engine.__new__(Engine);e.lock=threading.RLock();e.source='simulation';e.session=dict(running=True,protocol='speller',trials_planned=960);e.events=[]
        with self.assertRaisesRegex(ValueError,'target label'):
            e.event(dict(kind='stimulus',onset=time.time(),index=0,condition_index=0,speller=dict(group=8,line=0,target=3,phase='spelling')))

class AdaptiveSpellerTests(unittest.TestCase):
    def test_electrodes_learn_distinct_training_windows(self):
        from speller import model_windows
        rows=SpellerTests().rows();rng=np.random.default_rng(54)
        for r in rows:
            target=r['line'] in (r['target']//6,6+r['target']%6)
            r['features']={ch:rng.normal(0,.1,12)+target*np.array(signal) for ch,signal in [('TP9',[3]*4+[0]*8),('AF8',[0]*8+[-3]*4)]}
        windows=model_windows(fit(rows))
        self.assertLess(sum(windows['TP9']),sum(windows['AF8']))
        for lo,hi in windows.values():self.assertTrue(100<=hi-lo<=400)
        self.assertNotEqual(windows['TP9'],windows['AF8'])

    def test_saved_text_accumulates_retry_and_delete_are_consistent(self):
        from speller import request
        from unittest.mock import patch
        from types import SimpleNamespace
        import threading,copy
        e=SimpleNamespace(lock=threading.RLock(),session={'protocol':'speller'},trials=[],events=[],source='simulation',speller_model={'test':True},process_pending=lambda:None)
        saved=[];e.save_metadata=lambda:saved.append(copy.deepcopy(e.session))
        def event(value):e.events.append(value);e.save_metadata()
        e.event=event
        with patch('speller.examples',return_value=[]),patch('speller.decode',side_effect=lambda *a:dict(symbol='A',row_margin=.4,column_margin=.3)):
            self.assertEqual(request(e,dict(action='predict',group=8))['text'],'A')
            self.assertEqual(request(e,dict(action='predict',group=9))['text'],'AA')
            self.assertEqual(request(e,dict(action='predict',group=9))['text'],'AA')
            self.assertEqual(len(e.session['speller_history']),2)
            self.assertEqual(saved[-1]['speller_text'],'AA')
            self.assertEqual(request(e,dict(action='delete'))['text'],'A')
            self.assertEqual(request(e,dict(action='predict',group=9))['text'],'A')
            self.assertEqual(len(e.session['speller_history']),1)
            self.assertEqual(request(e,dict(action='status'))['text'],'A')

    def test_window_selection_is_refit_inside_each_validation_fold(self):
        from speller import request,fit as real_fit
        from unittest.mock import patch
        from types import SimpleNamespace
        from pathlib import Path
        import tempfile,threading
        rows=SpellerTests().rows();training_groups=[]
        def tracked_fit(data):
            training_groups.append(set(r['group'] for r in data));return real_fit(data)
        e=SimpleNamespace(lock=threading.RLock(),session={'protocol':'speller','id':'synthetic'},trials=[],events=[],source='simulation',process_pending=lambda:None,save_metadata=lambda:None)
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'synthetic').mkdir()
            with patch('speller.examples',return_value=rows),patch('speller.fit',side_effect=tracked_fit),patch('private_storage.DATA_ROOT',Path(root)):
                result=request(e,{'action':'fit'})
        self.assertEqual(len(training_groups),9)
        for held_out,groups in enumerate(training_groups[1:]):self.assertEqual(groups,set(range(8))-{held_out})
        self.assertEqual(len(result['validation']),8)
        self.assertTrue(result['windows'])

class SpellerResultWindowTests(unittest.TestCase):
    def test_each_channel_uses_its_own_window_and_manual_override(self):
        from engine import Engine
        import threading
        e=Engine.__new__(Engine);e.lock=threading.RLock();e.events=[];e.pending=[];e.revision=0;e.cache_revision=None
        e.session=dict(id='abc',protocol='speller',mode='erp',channels=['TP9','AF8'],conditions=['Other','Cued'],minimum=10,metric='mean',window=[.3,.5],speller_windows_ms={'TP9':[100,300],'AF8':[500,700]})
        times=np.arange(-.2,.801,.01);wave=np.where((times>=.1)&(times<.3),2,np.where((times>=.5)&(times<.7),7,0))
        e.trials=[dict(index=i,speller={'phase':'calibration'},times=times.tolist(),condition_index=i%2,condition='test',accepted=True,wave=wave.tolist(),feature=-999,tf=None,reasons=[],channel_trials={ch:dict(accepted=True,feature=-999,wave=wave.tolist(),reasons=[]) for ch in ['TP9','AF8']}) for i in range(24)]
        a=e.analysis()['channels'];self.assertEqual(a['TP9']['window'],[.1,.3]);self.assertEqual(a['AF8']['window'],[.5,.7])
        self.assertAlmostEqual(a['TP9']['groups'][0]['mean'],2);self.assertAlmostEqual(a['AF8']['groups'][0]['mean'],7)
        self.assertFalse(a['TP9']['stats']['ready'])
        e.saved_view=lambda _:e
        r=e.result_window('abc',.5,.7,'TP9')
        self.assertEqual(r['analysis']['channels']['TP9']['window'],[.5,.7]);self.assertEqual(r['analysis']['channels']['AF8']['window'],[.5,.7])
        self.assertEqual(e.session['speller_windows_ms']['TP9'],[100,300])
        self.assertNotIn('speller_review_windows_ms',e.session)
