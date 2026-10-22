import json,tempfile,unittest
from pathlib import Path
from scripts.report_matrix_pilots import report
class PilotReportTests(unittest.TestCase):
 def test_private_fields_omitted_simulation_excluded_and_duplicate_session_ignored(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   row=dict(kind='matrix',id='same-session',source='live',participant_name='PRIVATE EXAMPLE',matrix_result={'answered':12},matrix_pilot_responses=[dict(version='bandstand-matrix-pilot-v1',item_id='bs-combine-01-v1',correct=True,timeout=False,seconds=4.25)])
   for n,record in enumerate([row,row,{**row,'id':'sim','source':'simulation'},{**row,'id':'partial','matrix_result':{'answered':3}}]):(root/f'record-{n}.json').write_text(json.dumps(record))
   output=report(root.glob('*.json'));encoded=json.dumps(output)
   self.assertEqual(output['sessions'],1);self.assertEqual(output['excluded_sessions'],2)
   self.assertEqual(output['items'][0]['responses'],1)
   self.assertNotIn('PRIVATE EXAMPLE',encoded);self.assertNotIn('same-session',encoded)
