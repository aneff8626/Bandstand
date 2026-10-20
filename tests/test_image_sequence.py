import random,unittest
from collections import Counter
from engine import image_sequence
class ImageSequenceTests(unittest.TestCase):
 def test_balanced_use_and_no_immediate_repeats(self):
  pool=[{'file':f'img{i}'} for i in range(20)]
  for seed in range(200):
   for n in (20,37,80,160):
    seq=image_sequence(pool,n,random.Random(seed));files=[a['file'] for a in seq]
    self.assertEqual(len(files),n)
    self.assertFalse(any(a==b for a,b in zip(files,files[1:])),'same image twice in a row')
    counts=Counter(files);self.assertLessEqual(max(counts.values())-min(counts.get(f'img{i}',0) for i in range(20)),1)
 def test_deterministic_for_a_seed(self):
  pool=[{'file':f'img{i}'} for i in range(25)]
  self.assertEqual(image_sequence(pool,60,random.Random(5)),image_sequence(pool,60,random.Random(5)))
