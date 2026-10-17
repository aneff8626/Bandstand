import tempfile,unittest
from pathlib import Path
from report import make_report
BASE=dict(id='20261017-000000-abcdef',title='Synthetic test session',source='simulation',channels=['AF7','AF8'],metric='amplitude',window=[.2,.35],band=[8,13],
 running=False,end_reason='completed',seed=7,thresholds={'peak_to_peak':180},notes='Synthetic.',timing='Software timestamps.',analysis='Test processing note.',trials_planned=4,mode='erp')
STATS=dict(ready=True,t=-3.21,df=17.4,p=.0042,label='**')
class ReportBuildTests(unittest.TestCase):
 def build(self,session,analysis,events):
  with tempfile.TemporaryDirectory() as d:
   data=make_report(session,analysis,events,Path(d));self.assertTrue(data.startswith(b'%PDF'));return data
 def test_erp_reports_with_behaviour(self):
  events=[{'kind':'stimulus','index':i,'condition_index':i%2} for i in range(4)]
  flanker={'groups':[{'label':'Congruent','accepted':2,'rejected':0,'mean':-1.2,'se':.4,'erp':{'mean':[0,-1,-2]}},{'label':'Incongruent','accepted':2,'rejected':0,'mean':-3.4,'se':.5,'erp':{'mean':[0,-2,-4]}}],
   'unit':'µV','times':[-.2,.3,.8],'stats':STATS,'rejections':[{'index':0,'condition':'Congruent','reasons':['probable blink']}],
   'behavior':{'kind':'flanker','conditions':[dict(label='Congruent',presented=2,responded=2,correct=2,errors=0,missed=0,accuracy=1.,median_rt_ms=410.),dict(label='Incongruent',presented=2,responded=1,correct=1,errors=0,missed=1,accuracy=.5,median_rt_ms=480.)],'congruency_rt_ms':70.,'note':'n'}}
  self.build({**BASE,'protocol':'flanker'},flanker,events)
  reward={**flanker,'behavior':{'kind':'reward','choices':3,'skipped':1,'wins':1,'blue_proportion':2/3,'by_choice':[dict(choice='blue',n=2,wins=1,win_rate=.5,median_rt_ms=600.),dict(choice='green',n=1,wins=0,win_rate=0.,median_rt_ms=None)],'note':'n'}}
  self.build({**BASE,'protocol':'reward'},reward,events)
 def test_tf_reports(self):
  tf={'groups':[],'unit':'dB','spectral':True,'band':[8.,13.],'channels':{'TP9':{'groups':[{'label':'Eyes open','accepted':10,'rejected':0,'clean_seconds':100.,'mean':1.2},{'label':'Eyes closed','accepted':10,'rejected':0,'clean_seconds':100.,'mean':4.4}],'stats':STATS}}}
  for protocol in ('alpha','disclosure'):self.build({**BASE,'protocol':protocol,'mode':'tf','window':[2.,12.]},tf,[])
