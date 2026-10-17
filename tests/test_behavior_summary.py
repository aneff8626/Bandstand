import unittest
from analysis import behavior_summary
def stim(i,c):return {'kind':'stimulus','index':i,'condition_index':c}
class BehaviorSummaryTests(unittest.TestCase):
 def test_flanker_accuracy_misses_and_rt(self):
  events=[stim(0,0),{'kind':'response','index':0,'correct':True,'rt_ms':400},stim(1,0),{'kind':'response','index':1,'correct':False,'rt_ms':300},
   stim(2,1),{'kind':'response','index':2,'correct':True,'rt_ms':500},stim(3,1),stim(4,1),{'kind':'response','index':4,'correct':True,'rt_ms':700}]
  b=behavior_summary('flanker',events);c,i=b['conditions']
  self.assertEqual((c['presented'],c['correct'],c['errors'],c['missed'],c['accuracy'],c['median_rt_ms']),(2,1,1,0,.5,400.))
  self.assertEqual((i['presented'],i['correct'],i['missed'],i['median_rt_ms']),(3,2,1,600.))
  self.assertAlmostEqual(i['accuracy'],2/3);self.assertEqual(b['congruency_rt_ms'],200.)
 def test_reward_choices_wins_and_skips(self):
  events=[{'kind':'response','index':0,'choice':'blue','rt_ms':650},stim(0,1),{'kind':'response','index':1,'choice':'blue','rt_ms':550},stim(1,0),
   {'kind':'note','index':2,'note':'No choice; trial skipped'},{'kind':'response','index':3,'choice':'green'},stim(3,0)]
  b=behavior_summary('reward',events);blue,green=b['by_choice']
  self.assertEqual((b['choices'],b['skipped'],b['wins']),(3,1,1));self.assertAlmostEqual(b['blue_proportion'],2/3)
  self.assertEqual((blue['n'],blue['wins'],blue['win_rate'],blue['median_rt_ms']),(2,1,.5,600.));self.assertEqual((green['n'],green['wins'],green['median_rt_ms']),(1,0,None))
 def test_biofeedback_math_pre_post(self):
  events=[{'kind':'behavior','phase':'pre','correct':True,'rt_ms':3000},{'kind':'behavior','phase':'pre','correct':False,'rt_ms':5000},{'kind':'behavior','phase':'post','correct':True,'rt_ms':2500}]
  pre,post=behavior_summary('biofeedback',events)['phases']
  self.assertEqual((pre['problems'],pre['correct'],pre['accuracy'],pre['median_rt_ms']),(2,1,.5,4000.));self.assertEqual((post['problems'],post['accuracy']),(1,1.))
 def test_other_tasks_have_no_behavior_block(self):
  self.assertIsNone(behavior_summary('oddball',[stim(0,1)]))
