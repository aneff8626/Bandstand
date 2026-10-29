import os
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from participant_context import participant_context
class ParticipantContextTests(unittest.TestCase):
 def test_local_record_and_link(self):
  with tempfile.TemporaryDirectory() as tmp:
   e=SimpleNamespace(session={'id':'abc'},typing=SimpleNamespace(session=None),personal=SimpleNamespace(current=None))
   result=participant_context(tmp,'context',{'fields':{'subject':'Test participant'},'forms':[{'kind':'extraversion','answers':[3]*10,'skipped':False}]},e)
   p=Path(tmp)/'participant-context'/(result['id']+'.json')
   if os.name!='nt':self.assertEqual(p.stat().st_mode&0o777,0o600)
   self.assertEqual(json.loads(p.read_text())['forms'][0]['scores']['Extraversion'],3)
   participant_context(tmp,'context-link',{'context_id':result['id'],'session_id':'abc','kind':'start'},e)
   self.assertEqual(json.loads(p.read_text())['session_id'],'abc')
   self.assertNotIn('subject',e.session)
   with self.assertRaises(ValueError):participant_context(tmp,'context-link',{'context_id':'../../x','session_id':'abc','kind':'start'},e)
 def test_skipped_and_invalid(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=participant_context(tmp,'context',{'fields':{},'forms':[{'kind':'big5','answers':[None,3],'skipped':True}]},None)
   row=json.loads((Path(tmp)/'participant-context'/(r['id']+'.json')).read_text())
   self.assertNotIn('scores',row['forms'][0])
   with self.assertRaises(ValueError):participant_context(tmp,'context',{'fields':{'age':'-2'}},None)
