import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from sequence_decoder import channel_quality,context_tokens,make_transformer,fit_context
from typing_lab import TypingLab

class SequenceTests(unittest.TestCase):
 def data(self):
  t=np.arange(35*256)/256;rg=np.random.default_rng(66);x=rg.normal(0,2,(len(t),4))+5*np.sin(2*np.pi*10*t[:,None]+np.arange(4));return t,x
 def test_one_bad_channel_does_not_reject_word(self):
  t,x=self.data();x[:,1]=1000;s,q,p,r=context_tokens(t,x,x,34,30)
  self.assertTrue(r['usable']);self.assertNotIn('AF7',r['channels']);self.assertTrue((q[:,1]==0).all());self.assertEqual(s.shape,(120,4,10))
 def test_all_bad_channels_abstain(self):
  t,x=self.data();x[:]=1000;s,q,p,r=context_tokens(t,x,x,34,30);self.assertFalse(r['usable'])
 def test_future_eeg_cannot_affect_pre_onset_context(self):
  t,x=self.data();s,q,p,r=context_tokens(t,x,x,30,10);x[t>=30]=900;s2,q2,p2,r2=context_tokens(t,x,x,30,10);np.testing.assert_equal(s,s2);np.testing.assert_equal(q,q2)
 def test_local_noise_masks_only_affected_segments(self):
  t,x=self.data();x[256:320,2]=1000;q,reasons=channel_quality(x,t);self.assertTrue((q[256:320,2]==0).all());self.assertTrue((q[:256,2]>0).all());self.assertTrue((q[256:320,0]>0).all())
 def test_attention_mask_prevents_hidden_signal_leakage(self):
  torch.manual_seed(7);net=make_transformer(2).eval();x=torch.randn(2,120,4,10);q=torch.ones(2,120,4);q[:,:,1]=0;q[:,:15]=0;p=torch.arange(120)[None].expand(2,-1).float()*.5-60
  with torch.no_grad():
   a=net(x,q,p);x[:,:,1]=1e6;x[:,:15]=-1e6;b=net(x,q,p)
  self.assertTrue(torch.isfinite(a).all());torch.testing.assert_close(a,b)
 def test_time_encoding_and_distant_gradients(self):
  torch.manual_seed(7);net=make_transformer(2).eval();x=torch.randn(1,120,4,10,requires_grad=True);q=torch.ones(1,120,4);p=torch.arange(120)[None].float()*.5-60
  a=net(x,q,p);b=net(x,q,p*2);self.assertGreater(float((a-b).abs().sum().detach()),1e-5);a.sum().backward();self.assertGreater(float(x.grad[:,:20].abs().sum()),0)
 def test_actual_training_updates_attention(self):
  torch.manual_seed(6);net=make_transformer(2);opt=torch.optim.AdamW(net.parameters(),lr=.002)
  x=torch.randn(8,120,4,10)*.05;y=torch.arange(8)%2;x[:,:30]+=torch.where(y[:,None,None,None]==0,-2.,2.);q=torch.ones(8,120,4);p=torch.arange(120)[None].expand(8,-1).float()*.5-60
  losses=[]
  for _ in range(12):
   opt.zero_grad();loss=torch.nn.functional.cross_entropy(net(x,q,p),y);loss.backward();opt.step();losses.append(float(loss.detach()))
  self.assertLess(min(losses[-4:]),losses[0])
 def test_no_model_before_enough_data(self):
  with tempfile.TemporaryDirectory() as root:
   model,report=fit_context([],root,1);self.assertIsNone(model);self.assertFalse(report['ready'])
 def test_native_keys_need_explicit_session_and_boundary(self):
  with tempfile.TemporaryDirectory() as root:
   lab=TypingLab(root)
   self.assertEqual(lab.native_event({'kind':'key','text':'x'},[],[],[]),{})
   with patch('typing_lab.time.time',return_value=100):
    lab.start(capture='system')
    def key(text,code=0):lab.native_event(dict(kind='key',text=text,keycode=code,onset=100,app='test.editor'),[],[],[])
    key('x');self.assertIsNone(lab.native_word)
    key(' ');key('h');key('i');key(' ')
    self.assertEqual(next(iter(lab.pending.values()))['label'],'hi')
    key('n');lab.native_event(dict(kind='boundary',onset=100),[],[],[])
    self.assertTrue(list(lab.pending.values())[-1]['cancelled']);lab.stop()
