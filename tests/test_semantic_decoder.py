import unittest,tempfile,sys,gzip,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from semantic_decoder import phrase_examples,eeg_summary,fit_semantic,SemanticModel,MAX_WORDS
from typing_lab import TypingLab
class SemanticTests(unittest.TestCase):
 def row(self,i,**extra):
  r=dict(onset=i,committed=i+.1,session='s',typed='word',label='word',accepted={'context':True},context_file='x.npz',context_block='b',focus_id='one');r.update(extra);return r
 def test_phrase_boundary_and_no_word_repetition_required(self):
  rows=[self.row(i,typed=t,label=t) for i,t in enumerate(['I','like','trees.','Today','is','sunny.'])]
  p=phrase_examples(rows);self.assertEqual(len(p),2);self.assertEqual(p[0]['onset'],0);self.assertEqual(p[1]['previous'],'I like trees.')
 def test_focus_changes_and_bad_edits_break_phrases(self):
  rows=[self.row(i,focus_id=str(i//2)) for i in range(12)];self.assertEqual(phrase_examples(rows),[])
  rows=[self.row(i,unsupported=i==2) for i in range(5)];self.assertEqual(phrase_examples(rows),[])
 def test_masked_values_do_not_affect_features(self):
  x=np.ones((120,4,10));q=np.ones((120,4));q[:,1]=0;p=np.arange(120)*.5-59.75
  a,_=eeg_summary(x,q,p);x[:,1]=np.nan;b,_=eeg_summary(x,q,p);np.testing.assert_equal(a,b)
 def test_model_keeps_training_candidates_out_of_validation(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);rows=[];rng=np.random.default_rng(7)
   for block in range(20):
    for phrase in range(4):
     onset=block*120+phrase*15;name=f'{block}-{phrase}.npz';v=rng.normal(size=(120,4,10)).astype('f');np.savez_compressed(root/name,sequence=v,quality=np.ones((120,4)),positions=np.arange(120)*.5-59.75)
     for j in range(3):rows.append(self.row(onset+j,typed=f'{block}-{phrase}-{j}'+('.' if j==2 else ''),context_file=name,context_block=str(block)))
   def embed(texts):
    import hashlib
    return np.array([np.random.default_rng(int.from_bytes(hashlib.sha256(t.encode()).digest()[:4],'big')).normal(size=16) for t in texts],dtype='f')/4
   path,r=fit_semantic(rows,root,1,encoder=embed);self.assertIsNotNone(path);m=SemanticModel(path);self.assertTrue(all(int(t.split('-')[0])<12 for t in m.texts));self.assertFalse(r['ready']);self.assertEqual(r['validation_blocks'],8)
 def test_compressed_recording_roundtrip(self):
  with tempfile.TemporaryDirectory() as root:
   lab=TypingLab(root);lab.start(capture='system');lab.ingest([1],[[1,2,3,4]],[[5,6,7,8]]);lab.stop()
   text=gzip.open(lab.directory/'continuous.csv.gz','rt').read();self.assertIn('1.0,1,2,3,4,5,6,7,8',text);self.assertEqual(lab.rows.maxlen,MAX_WORDS)
if __name__=='__main__':unittest.main()

class ProvisionalTests(unittest.TestCase):
 def test_early_model_is_unvalidated_and_uses_real_embeddings(self):
  from semantic_decoder import provisional
  with tempfile.TemporaryDirectory() as tmp:
   rng=np.random.default_rng(3);phrases=[dict(text='phrase '+str(i)) for i in range(8)]
   path,report=provisional(phrases,rng.normal(size=(8,320)),tmp,1,{},lambda texts:rng.normal(size=(len(texts),16)))
   self.assertIsNotNone(path);self.assertFalse(report['ready']);self.assertTrue(report['provisional']);self.assertFalse(SemanticModel(path).ready)

class PerformanceTests(unittest.TestCase):
 def test_four_choice_correctness_and_ties(self):
  from semantic_decoder import four_choice_scores
  target=np.eye(6);r=four_choice_scores(target,target,{'zero':np.zeros_like(target)},list('abcdef'))
  self.assertEqual(r['eeg'],1);self.assertEqual(r['correct'],6);self.assertEqual(r['n'],6);self.assertEqual(r['zero'],0);self.assertEqual(r['chance'],.25)
 def test_four_choice_requires_distinct_texts(self):
  from semantic_decoder import four_choice_scores
  self.assertIsNone(four_choice_scores(np.eye(3),np.eye(3),{},['same']*3))
