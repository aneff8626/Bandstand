import hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from cumulative_semantic import connect,blob,cumulative_ridge,index_archive,fit_cumulative,block_split
from semantic_decoder import ridge,SemanticModel

class CumulativeTests(unittest.TestCase):
 def test_streaming_solver_matches_batch_and_keeps_old_examples(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=connect(tmp);rng=np.random.default_rng(9);x=rng.normal(size=(1100,8));y=rng.normal(size=(1100,6))
   for i in range(len(x)):db.execute('INSERT INTO examples VALUES (?,?,?,?,?,?,?,?,?,?)',(str(i),'s',i,i+.1,str(i),'',blob(x[i]),blob(x[i,:2]),blob(y[i]),blob(y[i])))
   db.commit();model,n=cumulative_ridge(db);expected=ridge(x.astype('f'),y.astype('f'))
   self.assertEqual(n,1100)
   for a,b in zip(model,expected):np.testing.assert_allclose(a,b,atol=2e-6)
   self.assertGreater(np.linalg.norm(model[2]-ridge(x[-512:],y[-512:])[2]),.01)
   db.close()
 def test_archive_backfill_restart_cache_and_all_session_training(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);calls=[]
   def encoder(texts):
    calls.extend(texts)
    return np.array([np.random.default_rng(int.from_bytes(hashlib.sha256(t.encode()).digest()[:4],'big')).normal(size=8) for t in texts],dtype='f')
   np.savez(root/'context.npz',sequence=np.ones((120,4,10)),quality=np.ones((120,4)),positions=np.arange(120)*.5-59.75)
   # 3,240 words / 1,080 phrases: both old live-buffer limits are exceeded.
   for s in range(3):
    folder=root/str(s);folder.mkdir();rows=[]
    for i in range(1080):rows.append(dict(id=str(i),session=str(s),onset=s*10000+i,committed=s*10000+i+.1,typed=f'{s}-{i}'+('.' if i%3==2 else ''),label=f'{s}-{i}',accepted={'context':True},context_file='context.npz',focus_id='a'))
    (folder/'trials.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   db=connect(root);db.execute('INSERT INTO metadata VALUES (?,?)',('evaluation_block_seed','test-seed'));db.commit();db.close();path,r=fit_cumulative(root,1,encoder);self.assertEqual(r['training_phrases'],1080);self.assertEqual(r['archive_sessions'],3);self.assertGreaterEqual(r['validation_sessions'],1);self.assertEqual(r['evaluation_method'],'random-time-blocks-v1');self.assertLess(r['evaluation_training_phrases'],r['training_phrases']);self.assertEqual(len(SemanticModel(path).texts),256)
   calls.clear();db=connect(root);index_archive(root,db,encoder);self.assertEqual(calls,[]);self.assertEqual(db.execute('SELECT count(*) FROM examples').fetchone()[0],1080);db.close()
   # Changed/deleted source rows must not survive a rebuild of that session.
   (root/'0/trials.jsonl').write_text('');db=connect(root);index_archive(root,db,encoder);self.assertEqual(db.execute('SELECT count(*) FROM examples').fetchone()[0],720);db.close()
 def test_block_assignments_stable_and_eeg_support_disjoint(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=connect(tmp)
   for i in range(500):db.execute('INSERT INTO examples VALUES (?,?,?,?,?,?,?,?,?,?)',(str(i),'s',i*10,i*10+3,str(i),'',blob([1]),blob([1]),blob([1]),blob([1])))
   db.execute('INSERT INTO metadata VALUES (?,?)',('evaluation_block_seed','test-seed'));db.commit();block_split(db);first=dict(db.execute('SELECT id,role FROM eval_split'))
   self.assertIn('test',first.values());self.assertIn('train',first.values());self.assertIn('gap',first.values())
   block_split(db);self.assertEqual(first,dict(db.execute('SELECT id,role FROM eval_split')))
   train=db.execute("SELECT onset,end FROM examples WHERE id IN (SELECT id FROM eval_split WHERE role='train')").fetchall()
   test=db.execute("SELECT onset,end FROM examples WHERE id IN (SELECT id FROM eval_split WHERE role='test')").fetchall()
   for a,b in train:
    for c,d in test:self.assertTrue(b+1<=c-60 or d+1<=a-60)
   db.close()
if __name__=='__main__':unittest.main()
