"""Causal EEG transformer with real-time positions and channel/segment masks.
No text, application identity or key intervals enter the neural model.
"""
import math,json
from pathlib import Path
from collections import Counter
import numpy as np
from analysis import FS,CHANNELS

TOKEN_SECONDS=.5
MAX_SECONDS=60
FEATURES_PER_CHANNEL=10

def channel_quality(raw,times):
 """Local 250 ms decisions, rather than all-or-nothing word rejection."""
 x=np.asarray(raw,float);t=np.asarray(times,float);q=np.ones(x.shape,dtype=np.float32);q[~np.isfinite(x)]=0
 reasons={c:[] for c in CHANNELS}
 for start in range(0,len(x),64):
  block=x[start:start+64]
  if len(block)<16:continue
  for ch,c in enumerate(CHANNELS):
   v=block[:,ch];finite=np.isfinite(v)
   if not finite.all():q[start:start+len(block),ch]=0;reasons[c].append('missing samples');continue
   if np.max(abs(v))>=995:q[start:start+len(block),ch]=0;reasons[c].append('clipping');continue
   if np.std(v)<.2:q[start:start+len(block),ch]=0;reasons[c].append('flat signal');continue
   spectrum=abs(np.fft.rfft((v-v.mean())*np.hanning(len(v))))**2;f=np.fft.rfftfreq(len(v),1/FS)
   high=spectrum[(f>=25)&(f<=45)].sum();total=max(spectrum[(f>=1)&(f<=45)].sum(),1e-9)
   rms=math.sqrt(high*2/max(np.sum(np.hanning(len(v))**2)*len(v),1))
   if high/total>.55 and rms>18:q[start:start+len(block),ch]=0;reasons[c].append('high-frequency noise');continue
   if np.ptp(v)>300 or np.max(abs(np.diff(v)))>80:q[start:start+len(block),ch]=0;reasons[c].append('large transient');continue
   if np.ptp(v)>150:q[start:start+len(block),ch]*=.35;reasons[c].append('downweighted transient')
 if len(t)>1:
  for k in np.flatnonzero(np.diff(t)>1.75/FS):q[max(0,k-1):min(len(q),k+3)]=0
 return q,{c:sorted(set(v)) for c,v in reasons.items() if v}

def context_tokens(times,raw,filtered,onset,history=30,delay=0):
 """120 half-second tokens, ending at the chosen causal inference cutoff."""
 t=np.asarray(times,float);x=np.asarray(raw,float);y=np.asarray(filtered,float)
 end=onset+delay;start=end-history
 first=np.searchsorted(t,start);last=np.searchsorted(t,end)
 t=t[first:last];x=x[first:last];y=y[first:last]
 seq=np.zeros((120,4,10),np.float32);quality=np.zeros((120,4),np.float32);positions=np.arange(-119,1,dtype=np.float32)*.5-.25+delay
 if len(t)<16:return seq,quality,positions,{'reason':'Waiting for EEG context','usable':False,'coverage':0.,'channels':[]}
 q,reasons=channel_quality(x,t)
 for token in range(120-int(history*2),120):
  lo=end+(token-120)*.5;hi=lo+.5;ids=np.flatnonzero((t>=lo)&(t<hi))
  if len(ids)<120 or np.any(np.diff(t[ids])>1.75/FS):continue
  for ch in range(4):
   good=(q[ids,ch]>0)&np.isfinite(y[ids,ch]);coverage=float(np.mean(q[ids,ch]))
   if good.sum()<64 or coverage<.4:continue
   values=np.interp(np.linspace(lo,hi,128,endpoint=False),t[ids][good],y[ids,ch][good]);quality[token,ch]=coverage
   slow=np.array_split(values,4);spec=abs(np.fft.rfft((values-values.mean())*np.hanning(128)))**2/(FS*np.sum(np.hanning(128)**2));freq=np.fft.rfftfreq(128,1/FS)
   seq[token,ch]=[*[v.mean() for v in slow],*[np.log1p(spec[(freq>=a)&(freq<b)].sum()*2) for a,b in [(2,4),(4,8),(8,13),(13,20),(20,40)]],np.log1p(np.std(values))]
 valid=(quality>=.4).sum(1)>=2;recent=valid[-8:]
 usable=int(valid.sum())>=4 and int(recent.sum())>=2
 channels=[CHANNELS[ch] for ch in range(4) if float(np.mean(quality[-8:,ch]))>=.2]
 return seq,quality,positions,dict(usable=bool(usable),coverage=float(np.mean(quality[-int(history*2):])),channels=channels,channel_reasons=reasons,reason='Usable channels retained; noisy segments masked' if usable else 'Not enough usable EEG on two channels')

def _torch():
 import torch
 torch.set_num_threads(1)
 return torch

def make_transformer(classes):
 torch=_torch();nn=torch.nn
 class EEGTransformer(nn.Module):
  def __init__(self):
   super().__init__();self.channel_embed=nn.Parameter(torch.randn(4,48)*.02);self.project=nn.Linear(10,48);self.cls=nn.Parameter(torch.randn(1,1,48)*.02)
   layer=nn.TransformerEncoderLayer(48,4,128,dropout=.15,activation='gelu',batch_first=True,norm_first=True)
   self.encoder=nn.TransformerEncoder(layer,2,enable_nested_tensor=False);self.norm=nn.LayerNorm(48);self.head=nn.Linear(48,classes)
   self.register_buffer('rates',torch.exp(torch.arange(0,48,2)*(-math.log(10000)/48)))
  def forward(self,x,q,seconds):
   # Normalize before this call, then zero masked channels; no masked EEG value can leak through.
   x=torch.where(q[...,None]>0,x,torch.zeros_like(x));embedded=self.project(x)+self.channel_embed
   weights=q[...,None];h=(embedded*weights).sum(2)/weights.sum(2).clamp_min(1)
   positional=torch.zeros_like(h);positional[:,:,0::2]=torch.sin(seconds[...,None]*self.rates);positional[:,:,1::2]=torch.cos(seconds[...,None]*self.rates);h=h+positional
   h=torch.cat([h,self.cls.expand(len(h),-1,-1)],1)
   invalid=(q>=.4).sum(2)<2;invalid=torch.cat([invalid,torch.zeros((len(h),1),dtype=torch.bool,device=h.device)],1)
   # A safe always-valid first token avoids all-masked causal prefixes; it contains no EEG.
   h=torch.cat([torch.zeros_like(h[:,:1]),h],1);invalid=torch.cat([torch.zeros_like(invalid[:,:1]),invalid],1)
   causal=torch.triu(torch.ones((h.shape[1],h.shape[1]),dtype=torch.bool,device=h.device),diagonal=1)
   out=self.encoder(h,mask=causal,src_key_padding_mask=invalid,is_causal=True)
   return self.head(self.norm(out[:,-1]))
 return EEGTransformer()

class SequenceModel:
 def __init__(self,net,mean,scale,classes,look=0):self.net=net.eval();self.mean=mean;self.scale=scale;self.classes=classes;self.look=look
 def scores(self,seq,q,pos):
  torch=_torch()
  with torch.inference_mode():
   z=np.clip((seq-self.mean)/self.scale,-8,8).astype(np.float32)
   return torch.softmax(self.net(torch.from_numpy(z),torch.from_numpy(q.astype(np.float32)),torch.from_numpy(pos.astype(np.float32))),-1).numpy()
 def predict(self,seq,q,pos):
  scores=self.scores(seq[None],q[None],pos[None])[0];order=np.argsort(scores);best=order[-1]
  # Softmax scores are not presented as calibrated probabilities.
  margin=float(scores[best]-scores[order[-2]])
  valid=q>0;z=np.abs((seq-self.mean)/self.scale);outlier=float(np.mean(z[valid]>5)) if valid.any() else 1
  return dict(word=self.classes[best] if margin>=.15 and outlier<.1 else None,margin=margin,model_look=self.look,reason='Temporal transformer · exploratory' if margin>=.15 and outlier<.1 else 'Temporal estimate is ambiguous')

def load_examples(rows,root):
 kept=[];sequences=[];masks=[];positions=[]
 for r in rows:
  if not r.get('label') or not r.get('accepted',{}).get('context') or r.get('cancelled') or r.get('unsupported'):continue
  try:
   z=np.load(Path(root)/r['context_file'],allow_pickle=False)
   sequences.append(z['sequence']);masks.append(z['quality']);positions.append(z['positions']);kept.append(r)
  except (OSError,KeyError,ValueError):continue
 return kept,np.asarray(sequences,np.float32),np.asarray(masks,np.float32),np.asarray(positions,np.float32)

def fit_context(rows,root,look):
 torch=_torch();rows=sorted(rows,key=lambda r:r['onset']);rows,x,q,pos=load_examples(rows,root)
 blocks=list(dict.fromkeys(r['context_block'] for r in rows));report=dict(ready=False,reason='Collecting recurring words across at least 8 training and 8 later two-minute blocks.',architecture='2-layer causal transformer, 4 attention heads, 48 hidden units; real-time positional encoding; channel and time masks',look=look,blocks=len(blocks))
 if len(blocks)<16:return None,report
 split=min(max(8,int(len(blocks)*.65)),len(blocks)-8);valblocks=set(blocks[split:]);boundary=min(r['onset'] for r in rows if r['context_block'] in valblocks)
 train=[i for i,r in enumerate(rows) if r['context_block'] not in valblocks and r['onset']+1<boundary-60]
 counts=Counter(rows[i]['label'] for i in train);classes=[c for c,n in counts.most_common(12) if n>=30]
 if len(classes)<2:report['reason']='Need at least 30 usable training examples of each of two recurring words.';return None,report
 train=[i for i in train if rows[i]['label'] in classes];val=[i for i,r in enumerate(rows) if r['context_block'] in valblocks and r['label'] in classes];vc=Counter(rows[i]['label'] for i in val)
 report.update(classes=classes,training_counts=dict(Counter(rows[i]['label'] for i in train)),validation_counts=dict(vc))
 if any(vc[c]<10 for c in classes):report['reason']='Need 10 later validation examples per candidate word.';return None,report
 weights=q[train,...,None];den=weights.sum((0,1)).clip(1);mean=(x[train]*weights).sum((0,1))/den;scale=np.sqrt((((x[train]-mean)**2)*weights).sum((0,1))/den).clip(.01)
 torch.manual_seed(481);net=make_transformer(len(classes));optimizer=torch.optim.AdamW(net.parameters(),lr=.0007,weight_decay=.01)
 z=np.clip((x[train]-mean)/scale,-8,8).astype(np.float32);yt=torch.tensor([classes.index(rows[i]['label']) for i in train]);counts=np.bincount(yt.numpy(),minlength=len(classes));cw=torch.tensor(len(train)/(len(classes)*counts),dtype=torch.float32)
 loss_fn=torch.nn.CrossEntropyLoss(weight=cw);tx=torch.from_numpy(z);tq=torch.from_numpy(q[train]);tp=torch.from_numpy(pos[train]);rng=np.random.default_rng(481)
 net.train()
 # Fixed budget: later validation never determines epochs, normalization or hyperparameters.
 losses=[]
 for epoch in range(24):
  total=0
  for ids in np.array_split(rng.permutation(len(train)),max(1,math.ceil(len(train)/24))):
   optimizer.zero_grad();loss=loss_fn(net(tx[ids],tq[ids],tp[ids]),yt[ids]);loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),1.);optimizer.step();total+=float(loss.detach())
  losses.append(total)
 model=SequenceModel(net,mean,scale,classes,look);scores=np.concatenate([model.scores(x[ids],q[ids],pos[ids]) for ids in np.array_split(val,max(1,math.ceil(len(val)/32)))])
 predictions=np.array(classes)[scores.argmax(1)];truth=np.array([rows[i]['label'] for i in val]);correct=predictions==truth;majority=Counter(rows[i]['label'] for i in train).most_common(1)[0][0];chance=1/len(classes)
 accuracy=float(correct.mean());balanced=float(np.mean([correct[truth==c].mean() for c in classes]));deltas=[]
 for block in dict.fromkeys(rows[i]['context_block'] for i in val):
  ids=[j for j,i in enumerate(val) if rows[i]['context_block']==block]
  if len(ids)>=3:deltas.append(float(correct[ids].mean()-max(chance,np.mean(truth[ids]==majority))))
 wins=sum(v>0 for v in deltas);n=sum(v!=0 for v in deltas);p=sum(math.comb(n,k) for k in range(wins,n+1))/2**n if n else 1.;alpha=.01/(look*(look+1))
 ready=len(deltas)>=8 and accuracy>=.6 and balanced>=chance+.1 and p<=alpha
 # A separate nuisance baseline checks whether channel availability alone explains labels.
 from typing_lab import fit_ridge,predict
 mask_features=np.concatenate([q.mean(1),q.std(1),q[:,-8:].mean(1)],axis=1)
 nuisance=fit_ridge(mask_features[train],[rows[i]['label'] for i in train],classes)
 mask_accuracy=float(np.mean([predict(nuisance,mask_features[i])[0]==rows[i]['label'] for i in val]))
 ready=ready and accuracy>mask_accuracy+.05
 report.update(mask_only_accuracy=mask_accuracy,ready=ready,accuracy=accuracy,balanced_accuracy=balanced,chance=chance,majority_accuracy=float(np.mean(truth==majority)),validation_trials=len(val),validation_blocks=len(deltas),p_block_sign=p,alpha=alpha,training_epochs=24,reason='Exploratory temporal decoder passed later-block checks.' if ready else 'Temporal decoder has not passed later-block checks.',context_embargo_seconds=60)
 checkpoint=dict(state=net.state_dict(),mean=mean.tolist(),scale=scale.tolist(),classes=classes,look=look,report=report)
 torch.save(checkpoint,Path(root)/'transformer_checkpoint.pt')
 return model if ready else None,report
