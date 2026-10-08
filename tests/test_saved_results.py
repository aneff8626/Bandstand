import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from engine import Engine
class SavedResultsTests(unittest.TestCase):
 def test_saved_results_do_not_replace_acquisition_or_rewrite_metadata(self):
  with tempfile.TemporaryDirectory() as tmp,patch('engine.ROOT',Path(tmp)),patch('engine.DATA_ROOT',Path(tmp)/'data'):
   e=Engine();e.session={'id':'current','running':True};d=Path(tmp)/'data'/'20261007-abcd';d.mkdir()
   original=json.dumps({'id':d.name,'title':'Oddball','mode':'erp','channels':['TP10'],'conditions':['Standard','Target'],'minimum':10,'metric':'amplitude','running':False})
   (d/'session.json').write_text(original);(d/'trials.json').write_text('[]')
   v=e.saved_view(d.name);self.assertEqual(v.analysis()['trial_count'],0);v.export('processed')
   self.assertEqual(e.session['id'],'current');self.assertEqual((d/'session.json').read_text(),original)
   with self.assertRaises(ValueError):e.saved_view('../private')
