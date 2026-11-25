import unittest
import numpy as np
from cursor import fit,decode,step,distance,helpful,bits_per_move,calibration_quality,task_summary,ARROWS,FLASHES

CUES=[0,1,2,3,2,0,3,1]

class CursorDecoderTests(unittest.TestCase):
    def rows(self,seed=1):
        rng=np.random.default_rng(seed);rows=[]
        for group,target in enumerate(CUES):
            for rep in range(10):
                for arrow in range(4):
                    attended=arrow==target
                    features={'TP10':rng.normal(0,.4,14)+np.array([0,0,0,1,2,3,3,2,1,0,0,0,0,0])*attended}
                    rows.append(dict(features=features,group=group,arrow=arrow,target=target,phase='calibration'))
        return rows
    def test_held_out_move_and_bad_channels(self):
        rows=self.rows()
        for group in range(8):
            train=[r for r in rows if r['group']!=group];test=[r for r in rows if r['group']==group]
            model=fit(train);self.assertEqual(list(model),['TP10'])
            self.assertEqual(decode(test,model)['direction'],test[0]['target'])
    def test_prediction_does_not_read_target(self):
        rows=self.rows();model=fit(rows)
        test=[dict(r,target=None,phase='moving') for r in rows if r['group']==2]
        self.assertEqual(decode(test,model)['direction'],CUES[2])
    def test_missing_arrow_abstains(self):
        rows=self.rows();model=fit(rows)
        result=decode([r for r in rows if r['group']==0 and r['arrow']!=3],model)
        self.assertIsNone(result['direction']);self.assertIn('every arrow',result['reason'])
    def test_insufficient_training_and_null_model(self):
        self.assertEqual(fit(self.rows()[:20]),{})
        self.assertIsNone(decode(self.rows(),{})['direction'])
    def test_margin_is_gap_to_runner_up(self):
        rows=self.rows();result=decode([r for r in rows if r['group']==1],fit(rows))
        ordered=sorted(result['scores']);self.assertAlmostEqual(result['margin'],ordered[-1]-ordered[-2])
        self.assertEqual(result['arrow'],ARROWS[result['direction']])

class CursorTaskTests(unittest.TestCase):
    def test_moves_stay_inside_the_grid(self):
        self.assertEqual(step([3,3],0),[3,2]);self.assertEqual(step([3,3],1),[4,3])
        self.assertEqual(step([0,0],0),[0,0]);self.assertEqual(step([0,0],3),[0,0]);self.assertEqual(step([6,6],1),[6,6])
    def test_helpful_arrows_set_chance(self):
        self.assertEqual(helpful([3,3],[6,3]),1)   # straight line: only right helps
        self.assertEqual(helpful([3,3],[5,5]),2)   # diagonal: right and down help
        self.assertEqual(distance([0,0],[2,3]),5)
    def test_bits_per_move(self):
        self.assertEqual(bits_per_move(.25),0.0);self.assertEqual(bits_per_move(.1),0.0);self.assertAlmostEqual(bits_per_move(1),2.0)
        self.assertAlmostEqual(bits_per_move(.5),2+.5*np.log2(.5)+.5*np.log2(.5/3))
    def test_quality_uses_four_choice_chance(self):
        good=[dict(expected=i%4,predicted=i%4 if i<6 else (i+1)%4,auc=.8) for i in range(8)]
        q=calibration_quality(good);self.assertTrue(q['ready']);self.assertEqual((q['correct'],q['total']),(6,8))
        self.assertAlmostEqual(q['bits_per_minute'],bits_per_move(.75)*60/q['seconds_per_move'])
        weak=[dict(p,predicted=(p['expected']+1)%4) for p in good];self.assertFalse(calibration_quality(weak)['ready'])
    def test_task_summary(self):
        moves=[dict(target_number=1,start=[3,3],target=[6,3],end=[4,3],direction=1,toward=True,helpful=1,reached=False),
               dict(target_number=1,start=[4,3],target=[6,3],end=[4,3],direction=None,toward=False,helpful=1,reached=False),
               dict(target_number=2,start=[4,3],target=[4,5],end=[4,4],direction=2,toward=True,helpful=1,reached=False),
               dict(target_number=2,start=[4,4],target=[4,5],end=[4,5],direction=2,toward=True,helpful=1,reached=True)]
        s=task_summary(moves)
        self.assertEqual([t['fewest'] for t in s['targets']],[3,2]);self.assertEqual(s['reached'],1)
        self.assertEqual((s['moves'],s['decided'],s['toward']),(4,3,3));self.assertAlmostEqual(s['chance_toward'],.75)

class CursorEngineTests(unittest.TestCase):
    def engine(self,root):
        import threading,engine
        (root/'s').mkdir(exist_ok=True)
        e=engine.Engine.__new__(engine.Engine);e.lock=threading.RLock();e.source='simulation';e.events=[];e.pending=[]
        e.session=dict(id='s',running=True,protocol='cursor',trials_planned=2400,conditions=['Unattended','Attended'])
        return e
    def test_flash_validation(self):
        import tempfile,pathlib,time,engine
        from unittest import mock
        with tempfile.TemporaryDirectory() as root,mock.patch.object(engine,'DATA_ROOT',pathlib.Path(root)):
            e=self.engine(pathlib.Path(root));t=time.time()
            e.event(dict(kind='stimulus',onset=t,index=0,condition_index=1,cursor=dict(group=0,arrow=2,target=2,phase='calibration')))
            e.event(dict(kind='stimulus',onset=t,index=1,condition_index=0,cursor=dict(group=59,arrow=3,target=None,phase='moving')))
            self.assertEqual(len(e.pending),2)
            with self.assertRaisesRegex(ValueError,'target label'):
                e.event(dict(kind='stimulus',onset=t,index=2,condition_index=0,cursor=dict(group=9,arrow=1,target=1,phase='moving')))
            with self.assertRaisesRegex(ValueError,'calibration target'):
                e.event(dict(kind='stimulus',onset=t,index=3,condition_index=0,cursor=dict(group=0,arrow=2,target=2,phase='calibration')))
            for bad in (dict(group=60,arrow=0),dict(group=0,arrow=4),dict(group='0',arrow=0)):
                with self.assertRaisesRegex(ValueError,'Invalid cursor flash'):
                    e.event(dict(kind='stimulus',onset=t,index=4,condition_index=0,cursor=dict(bad,target=None,phase='moving')))

class CursorRequestTests(unittest.TestCase):
    """Calibrate and move through cursor.request with synthetic flashes; the moving flashes carry no target."""
    def test_fit_then_move(self):
        import tempfile,pathlib,threading
        from types import SimpleNamespace
        from unittest import mock
        import private_storage,cursor
        times=np.arange(-51,206)/256;bump=np.exp(-((times-.4)/.08)**2)*6;rng=np.random.default_rng(3)
        events=[];trials=[];index=0
        def flash(group,arrow,phase,target,attended):
            nonlocal index
            events.append(dict(kind='stimulus',index=index,cursor=dict(group=group,arrow=arrow,phase=phase,target=target)))
            trials.append(dict(index=index,times=times,condition_index=int(phase=='calibration' and attended),
                               channel_trials={'TP10':dict(accepted=True,wave=rng.normal(0,1,len(times))+bump*attended)}))
            index+=1
        for group,target in enumerate(CUES):
            for rep in range(10):
                for arrow in range(4):flash(group,arrow,'calibration',target,arrow==target)
        for rep in range(10):
            for arrow in range(4):flash(8,arrow,'moving',None,arrow==1)   # the participant counts → (right)
        with tempfile.TemporaryDirectory() as root,mock.patch.object(private_storage,'DATA_ROOT',pathlib.Path(root)):
            (pathlib.Path(root)/'s').mkdir()
            e=SimpleNamespace(lock=threading.RLock(),session=dict(id='s',protocol='cursor',running=True),events=events,trials=trials,
                              source='simulation',process_pending=lambda:None,save_metadata=lambda:None,cache_revision=1)
            e.event=lambda ev:e.events.append(ev)
            with self.assertRaisesRegex(ValueError,'Calibrate before'):cursor.request(e,dict(action='move',group=8,position=[3,3],target=[6,3]))
            fitted=cursor.request(e,dict(action='fit'))
            self.assertEqual(fitted['quality']['total'],8);self.assertGreaterEqual(fitted['quality']['correct'],6)
            self.assertTrue((pathlib.Path(root)/'s'/'cursor-model.npz').exists())
            moved=cursor.request(e,dict(action='move',group=8,position=[3,3],target=[6,3],target_number=1))
            self.assertEqual(moved['move']['direction'],1);self.assertEqual(moved['move']['end'],[4,3]);self.assertTrue(moved['move']['toward'])
            again=cursor.request(e,dict(action='move',group=8,position=[0,0],target=[6,3],target_number=1))
            self.assertEqual(again['move']['end'],[4,3]);self.assertEqual(len(e.session['cursor_moves']),1)   # retries are idempotent
            with self.assertRaisesRegex(ValueError,'Invalid cursor cell'):cursor.request(e,dict(action='move',group=9,position=[7,0],target=[1,1]))
            self.assertEqual(FLASHES,40)

if __name__=='__main__':unittest.main()
