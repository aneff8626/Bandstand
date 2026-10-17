import tempfile,unittest
import numpy as np
from cumulative_semantic import connect,blob,SCHEMA
from shared_learning import local_round_update
from shared_model import ENCODER
class SharedLearningTests(unittest.TestCase):
 def test_consent_compatibility_all_examples_and_numeric_only_delta(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=connect(tmp)
   for i in range(700):db.execute('INSERT INTO examples VALUES (?,?,?,?,?,?,?,?,?,?)',(str(i),'s',i,i,'private text','',blob([1,2]),blob([1]),blob([.5,.2]),blob([0,0])))
   db.commit();manifest=dict(feature_schema=SCHEMA,model_family='semantic-ridge-gradient-v1',encoder=ENCODER,round_id='test',parent_model_sha256='a'*64,clip_norm=.001)
   args=(db,manifest,np.zeros(2),np.ones(2),np.zeros((3,2)))
   with self.assertRaises(PermissionError):local_round_update(*args)
   update=local_round_update(*args,consent=True)
   self.assertEqual(update['examples'],700);self.assertLessEqual(float(np.linalg.norm(update['delta'])),.001001);self.assertFalse(update['transport_enabled']);self.assertNotIn('private text',repr(update));self.assertEqual(update['delta'].shape,(3,2))
   manifest['feature_schema']='other'
   with self.assertRaises(ValueError):local_round_update(*args,consent=True)
   db.close()
