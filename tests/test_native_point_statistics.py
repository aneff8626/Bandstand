import ast,threading,unittest
from pathlib import Path
from types import SimpleNamespace
import test_point_statistics as fixtures
from point_statistics import request_point_statistics

class NativeStatisticsTests(unittest.TestCase):
 def test_native_dispatch_matches_http_helper(self):
  trials,session=fixtures.PointStatisticsTests().erp()
  view=SimpleNamespace(lock=threading.RLock(),trials=trials,session=session,analysis=lambda:None)
  engine=SimpleNamespace(saved_view=lambda ident:view)
  tree=ast.parse(Path('desktop_service.py').read_text())
  dispatch=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='dispatch')
  namespace={'engine':engine}
  exec(compile(ast.Module(body=[dispatch],type_ignores=[]),'desktop_service.py','exec'),namespace)
  path='point-statistics/test?low=-200&high=800&first=0&second=1&correction=none&full=true&domain=points'
  native=namespace['dispatch'](path,None)
  self.assertEqual(native,request_point_statistics(engine,'/api/'+path))
  self.assertTrue(native['channels']['AF7']['points'][1]['significant'])
 def test_single_erp_timepoint_uses_nearest_sample(self):
  from engine import Engine
  from unittest.mock import patch
  trial=dict(accepted=True,wave=[1,5,9],times=[0,.1,.2],channel_trials={'AF7':dict(accepted=True,wave=[2,6,10])})
  session=dict(mode='erp',window=[.1,.2],metric='amplitude',polarity='positive')
  view=SimpleNamespace(lock=threading.RLock(),trials=[trial],session=session)
  fake=SimpleNamespace(saved_view=lambda ident:view)
  with patch.object(Engine,'analysis',lambda self:{'features':[self.trials[0]['feature'],self.trials[0]['channel_trials']['AF7']['feature']]}):
   result=Engine.result_window(fake,'test',.094,.094)
  self.assertEqual(result['session']['window'],[.1,.1])
  self.assertEqual(result['analysis']['features'],[5,6])
