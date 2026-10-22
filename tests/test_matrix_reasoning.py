import unittest
from unittest.mock import patch
from matrix_reasoning import estimate, initialize, open_item, answer, eeg_demo

class MatrixTests(unittest.TestCase):
 def test_scores_and_uncertainty(self):
  self.assertIsNone(estimate([None]*12)['score'])
  low=estimate([2]*12); high=estimate([1]*12)
  self.assertLess(low['score'],100);self.assertGreater(high['score'],100)
  for r in (low,high):
   self.assertLess(r['interval'][0],r['score']);self.assertGreater(r['interval'][1],r['score'])
   self.assertEqual(r['answered'],12);self.assertFalse(r['partial'])
  self.assertEqual(estimate([1]+[None]*11)['correct'],1)
  for invalid in ([True]*12,[1]*11,[5]*12):
   with self.assertRaises(ValueError):estimate(invalid)
 def test_full_protocol_and_retry(self):
  r={};initialize(r,pilot_count=0)
  with patch('matrix_reasoning.time.time',return_value=100):
   first=open_item(r);self.assertEqual(first,open_item(r))
   self.assertEqual(sorted(c['value'] for c in first['choices']),[1,2,3,4])
   with self.assertRaises(ValueError):answer(r,first['token'],None)
   wrong=answer(r,first['token'],2);self.assertFalse(wrong['correct'])
   self.assertEqual(answer(r,first['token'],2),wrong)
   for _ in range(3):answer(r,open_item(r)['token'],1)
   self.assertEqual(r['matrix_state']['stage'],'test')
   self.assertEqual(r['matrix_result']['answered'],0)
   for _ in range(12):result=answer(r,open_item(r)['token'],1)
   self.assertTrue(result['complete']);self.assertIsNone(result['correct'])
   self.assertEqual(result['estimate']['correct'],12)
   with self.assertRaises(ValueError):open_item(r)
 def test_deadline_and_stale_response(self):
  r={};initialize(r,pilot_count=0);r['matrix_state']['stage']='test'
  with patch('matrix_reasoning.time.time',return_value=100):item=open_item(r)
  with patch('matrix_reasoning.time.time',return_value=131):
   result=answer(r,item['token'],1)
   self.assertEqual(result['estimate']['correct'],0);self.assertEqual(r['answers'][0],0)
   open_item(r)
   with self.assertRaises(ValueError):answer(r,'wrong-token',1)
 def test_demo_never_claims_validation(self):
  self.assertIsNone(eeg_demo({})['score'])
  result=eeg_demo({'phases':{'Questionnaire':{'AF7':{'n':3,'db':[2,5,3,1]}}}})
  self.assertTrue(result['synthetic']);self.assertIn('no demonstrated IQ accuracy',result['label'])
  self.assertNotIn('interval',result)
 def test_engine_completion_serializes_and_persists(self):
  import tempfile, json
  from types import SimpleNamespace
  from personal import PersonalActivities
  with tempfile.TemporaryDirectory() as tmp,patch('personal.time.time',return_value=1000),patch('matrix_reasoning.time.time',return_value=1000):
   p=PersonalActivities(tmp);e=SimpleNamespace(times=[1000],typing=SimpleNamespace(running=False),developer=SimpleNamespace(current=None),session=None,source='simulation')
   p.request('start',{'kind':'matrix'},e)
   for _ in range(18):
    opened=p.request('matrix-open',{},e)
    result=p.request('matrix-answer',{'token':opened['token'],'choice':1},e)
   json.dumps(result)
   self.assertIsNone(p.current)
   self.assertEqual(p.history()[0]['matrix_result']['correct'],12)
   self.assertTrue(p.history()[0]['matrix_eeg_demo']['synthetic'])
 def test_pilots_randomized_separate_and_versioned(self):
  from matrix_original import ITEMS as originals, item_hash
  plans=set()
  for _ in range(30):
   r={};initialize(r);plan=r['matrix_plan'];plans.add(str(plan))
   self.assertEqual(len(plan),15)
   self.assertEqual([e['index'] for e in plan if e['source']=='reference'],list(range(12)))
   pilots=[next(v for v in originals if v['id']==e['id']) for e in plan if e['source']=='original-pilot']
   self.assertEqual(len({v['family'] for v in pilots}),3)
  self.assertGreater(len(plans),1)
  r['matrix_state'].update(stage='test',index=0)
  with patch('matrix_reasoning.time.time',return_value=100):
   for entry in r['matrix_plan']:
    before=dict(r['matrix_result']);item=open_item(r)
    result=answer(r,item['token'],1)
    if entry['source']=='original-pilot':
     self.assertTrue(item['stem'].startswith('data:image/svg+xml;base64,'))
     self.assertEqual(before,r['matrix_result'])
   self.assertTrue(result['complete']);self.assertEqual(r['matrix_result']['answered'],12)
   self.assertEqual(len(r['matrix_pilot_responses']),3)
   for response in r['matrix_pilot_responses']:
    self.assertEqual(response['stimulus_sha256'],item_hash(next(v for v in originals if v['id']==response['item_id'])))
    self.assertEqual(sorted(response['option_order']),[1,2,3,4])
 def test_original_rule_answers_and_unique_options(self):
  from matrix_original import ITEMS as originals
  self.assertEqual(len(originals),12)
  for item in originals:
   self.assertEqual(item['options'][0],item['cells'][-1]);self.assertEqual(len(set(item['options'])),4)
   if item['family']!='count-turn':
    op={'combine':lambda a,b:a|b,'overlap':lambda a,b:a&b,'difference':lambda a,b:a^b}[item['family']]
    for row in range(3):
     a,b,c=item['cells'][row*3:row*3+3];self.assertEqual(op(a,b),c)
   else:
    for row in range(3):
     a,b,c=item['cells'][row*3:row*3+3]
     self.assertEqual(b[0],a[0]%3+1);self.assertEqual(c[0],b[0]%3+1)
     self.assertEqual((b[1]-a[1])%4,(c[1]-b[1])%4)
 def test_percentile_interval_and_legacy_plan(self):
  from matrix_reasoning import percentile
  self.assertAlmostEqual(percentile(0),50)
  self.assertAlmostEqual(percentile(1),84.1344746)
  result=estimate([1,2]*6)
  self.assertLess(result['percentile_interval'][0],result['reference_percentile'])
  self.assertGreater(result['percentile_interval'][1],result['reference_percentile'])
  r={};initialize(r,pilot_count=0);r.pop('matrix_plan');r['matrix_state']['stage']='test'
  with patch('matrix_reasoning.time.time',return_value=100):
   for _ in range(12):result=answer(r,open_item(r)['token'],1)
  self.assertTrue(result['complete'])
