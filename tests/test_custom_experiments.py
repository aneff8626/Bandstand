import unittest, tempfile, random, io, base64, wave, json, time
from pathlib import Path
from unittest.mock import patch
from collections import Counter
import numpy as np
from custom_experiments import validate_design,condition_order,import_media
class CustomExperiments(unittest.TestCase):
 def test_conditions_order_and_rejections(self):
  d=validate_design({'custom_design':{'conditions':['One','Two','Three'],'repetitions':3}},'tf')
  self.assertEqual(condition_order(d,random.Random(3)),[0,1,2]*3)
  d['order']='randomized';self.assertEqual(Counter(condition_order(d,random.Random(2))),{0:3,1:3,2:3})
  d['order']='custom';d['sequence']=[2,0,1];self.assertEqual(condition_order(d,random.Random(1)),[2,0,1]*3)
  for change in ({'conditions':['x','x']},{'duration_ms':100},{'repetitions':1.5},{'order':'custom','sequence':[0,0]},{'responses':[{'key':'Escape','meaning':'exit'}]},{'responses':[{'key':'f','meaning':'yes'},{'key':'F','meaning':'no'}]}):
   with self.assertRaises(ValueError):validate_design({'custom_design':{'conditions':['One','Two'],**change}},'tf')
 def test_default_label_only_erp(self):
  from engine import Engine
  from analysis import FS
  with tempfile.TemporaryDirectory() as tmp,patch('engine.DATA_ROOT',Path(tmp)):
   e=Engine();now=time.time();e.ingest(now-4+(np.arange(FS*4)+1)/FS,np.zeros((FS*4,4)))
   session=e.begin({'protocol':'custom_erp','allow_noisy_start':True,'custom_design':{'conditions':['Condition 1','Condition 2'],'media':[[],[]],'responses':[]}})
   self.assertEqual(set(t['condition'] for t in session['plan']),{'Condition 1','Condition 2'})
   self.assertTrue(all('asset' not in t for t in session['plan']))
   self.assertEqual(session['custom_design']['responses'],[])
   e.stop()
 def test_media_and_missing_assets(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as tmp,patch('custom_experiments.DATA_ROOT',Path(tmp)):
   im=io.BytesIO();Image.new('RGB',(20,20),'blue').save(im,format='PNG')
   image=import_media({'kind':'image','data':base64.b64encode(im.getvalue()).decode()})
   wav=io.BytesIO()
   with wave.open(wav,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0'*1600)
   audio=import_media({'kind':'audio','data':base64.b64encode(wav.getvalue()).decode()})
   d=validate_design({'custom_design':{'conditions':['Image','Audio'],'media':[[image['file']],[audio['file']]]}},'erp');self.assertEqual(len(d['media']),2)
   for value in ('../../secrets','custom-'+'0'*64+'.png'):
    with self.assertRaises(ValueError):validate_design({'custom_design':{'conditions':['a','b'],'media':[[value],[image['file']]]}},'erp')
 def test_engine_three_conditions_save(self):
  from engine import Engine
  from analysis import FS
  with tempfile.TemporaryDirectory() as tmp,patch('engine.DATA_ROOT',Path(tmp)):
   e=Engine();now=time.time()
   e.ingest(now-4+(np.arange(FS*4)+1)/FS,np.zeros((FS*4,4)))
   session=e.begin({'protocol':'custom','allow_noisy_start':True,'custom_design':{'conditions':['a','b','c'],'repetitions':2,'duration_ms':6000,'responses':[{'key':'f','meaning':'yes'}]}})
   self.assertEqual(len(session['plan']),6);self.assertEqual(session['window'],[2,6]);self.assertEqual(session['plan'][2]['condition_index'],2)
   e.event({'kind':'stimulus','index':2,'condition_index':2,'onset':now,'planned_duration_ms':6000})
   e.event({'kind':'response','index':2,'key':'f','meaning':'yes','rt_ms':25,'onset':now})
   result=e.analysis();self.assertEqual(len(result['channels']['AF7']['groups']),3);self.assertFalse(result['channels']['AF7']['stats']['ready'])
   e.stop();saved=json.loads((Path(tmp)/session['id']/'session.json').read_text());self.assertEqual(saved['custom_design']['responses'][0]['meaning'],'yes')
