"""Local semantic retrieval. Text supplies targets and a separate baseline only.
Frozen encoder runs in a short-lived CPU worker. Live inference is NumPy only.
"""
import os
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
import json,math,re,sys,resource,threading,time
from pathlib import Path
from collections import deque
import numpy as np
MAX_WORDS=3000
MAX_PHRASES=512
MEMORY_LIMIT=1536*1024*1024

def memory_check():
 rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 if sys.platform!='darwin':rss*=1024
 if rss>MEMORY_LIMIT:raise MemoryError('Semantic worker exceeded 1.5 GiB memory budget; recording continues')
 return rss

def phrase_examples(rows):
 """Non-overlapping 3–12 word phrases, split at punctuation, focus, or pauses.
EEG comes from the first word, before phrase text is available. No future EEG.
"""
 phrases=[];group=[];previous=None;prior_text=''
 def finish():
  nonlocal group,prior_text
  if len(group)>=3 and group[0].get('accepted',{}).get('context') and group[0].get('context_file'):
   text=' '.join(r.get('typed') or r['label'] for r in group)[:500]
   phrases.append(dict(text=text,previous=prior_text,context_file=group[0]['context_file'],onset=group[0]['onset'],end=group[-1].get('committed',group[-1]['onset']),block=group[0].get('context_block',group[0]['session']),session=group[0]['session']))
   prior_text=text
  group=[]
 for r in sorted(list(rows)[-MAX_WORDS:],key=lambda r:r['onset']):
  boundary=previous is not None and (r['session']!=previous['session'] or r.get('focus_id')!=previous.get('focus_id') or r['onset']-previous.get('committed',previous['onset'])>5)
  if boundary:finish();prior_text=''
  valid=r.get('label') and not any(r.get(k) for k in ('cancelled','unsupported','incomplete'))
  if not valid:finish();prior_text=''
  else:
   group.append(r)
   if len(group)>=12 or re.search(r'[.!?;:]\W*$',r.get('typed','')):finish()
  previous=r
 # A short trailing group is unfinished; don't invent a sentence boundary.
 return phrases[-MAX_PHRASES:]

def eeg_summary(seq,q,pos):
 """Masked multiscale temporal features at fixed seconds, independent of text."""
 seq=np.asarray(seq,float);q=np.asarray(q,float);pos=np.asarray(pos,float)
 out=[];mask=[]
 for lo,hi in [(-60,-30),(-30,-15),(-15,-8),(-8,-4),(-4,-2),(-2,-1),(-1,0),(0,1.01)]:
  ids=(pos>=lo)&(pos<hi);w=q[ids];x=np.where(w[...,None]>0,seq[ids],0)
  out.extend(((x*w[...,None]).sum(0)/np.maximum(w.sum(0)[:,None],1)).ravel())
  mask.extend(w.mean(0) if len(w) else np.zeros(4))
 return np.asarray(out,np.float32),np.asarray(mask,np.float32)

def unit(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-8)

def ridge(x,y):
 mean=x.mean(0);scale=x.std(0).clip(.1);z=np.clip((x-mean)/scale,-8,8);a=np.c_[z,np.ones(len(z))]
 penalty=np.eye(a.shape[1])*20;penalty[-1,-1]=1e-6
 return mean,scale,np.linalg.solve(a.T@a+penalty,a.T@y).astype(np.float32)

def apply(model,x):
 mean,scale,w=model;return unit(np.c_[np.clip((x-mean)/scale,-8,8),np.ones(len(x))]@w)

class SemanticModel:
 def __init__(self,path):
  with np.load(path,allow_pickle=False) as z:
   self.model=tuple(z[k].copy() for k in ('mean','scale','weights'));self.bank=z['bank'].copy();self.texts=z['texts'].tolist();self.ready=bool(z['ready']);self.look=int(z['look'])
 def predict(self,seq,q,pos):
  x,_=eeg_summary(seq,q,pos);v=apply(self.model,x[None])[0];scores=self.bank@v;ids=np.argsort(scores)[::-1][:3]
  outlier=float(np.mean(abs((x-self.model[0])/self.model[1])>5))
  candidates=[dict(text=self.texts[i],similarity=float(scores[i])) for i in ids] if outlier<.1 else []
  return dict(word=candidates[0]['text'] if self.ready and candidates else None,candidates=candidates,validated=self.ready,model_look=self.look,reason=('Semantic retrieval · held-out checks passed' if self.ready else 'Unvalidated semantic matches · similarity is not probability') if candidates else 'EEG outside training range; no semantic match')

def encode(texts):
 import torch
 from transformers import AutoTokenizer,AutoModel
 torch.set_num_threads(1)
 path=Path(__file__).parent/'models/all-MiniLM-L6-v2'
 tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True)
 model=AutoModel.from_pretrained(path,local_files_only=True,use_safetensors=True).eval()
 model.requires_grad_(False);out=[]
 for start in range(0,len(texts),8):
  batch=tokenizer(texts[start:start+8],padding=True,truncation=True,max_length=96,return_tensors='pt')
  with torch.inference_mode():
   h=model(**batch).last_hidden_state;w=batch['attention_mask'][...,None];v=(h*w).sum(1)/w.sum(1).clamp_min(1);out.append(torch.nn.functional.normalize(v,dim=1).numpy())
  memory_check()
 return np.concatenate(out)

def save_model(root,model,y,texts,look,ready=False):
 target=Path(root)/'semantic_checkpoint.npz';tmp=Path(root)/'semantic_checkpoint.tmp.npz'
 np.savez_compressed(tmp,mean=model[0],scale=model[1],weights=model[2],bank=y[-256:],texts=np.array(texts[-256:]),ready=ready,look=look);os.replace(tmp,target)
 return str(target)

def provisional(phrases,features,root,look,report,encoder):
 if len(phrases)<8 or len(set(r['text'].casefold() for r in phrases))<4:
  report['reason']='Need 8 usable phrases with at least 4 distinct texts for tentative matches.';return None,report
 y=encoder([r['text'] for r in phrases]);model=ridge(np.asarray(features),y)
 report.update(ready=False,provisional=True,training_phrases=len(phrases),validation_trials=0,reason='Ultra-tentative EEG phrase retrieval. Not yet validated; matches may be wrong.')
 return save_model(root,model,y,[r['text'] for r in phrases],look),report

def chance_range(n):
 if n<1:return None
 cdf=0.;low=None;high=None
 for k in range(n+1):
  cdf+=math.comb(n,k)*.25**k*.75**(n-k)
  if low is None and cdf>=.025:low=k
  if high is None and cdf>=.975:high=k
 return dict(low=low/n,high=high/n,minimum_above=high+1)

def four_choice_scores(pred,target,baselines,texts):
 # Same deterministic candidate choices for every method; no fitting on test targets.
 rng=np.random.default_rng(1729);hits={name:[] for name in ['eeg',*baselines]}
 vectors={'eeg':pred,**baselines}
 for i in range(len(target)):
  unique={}
  for j,text in enumerate(texts):
   if text.casefold()!=texts[i].casefold():unique.setdefault(text.casefold(),j)
  if len(unique)<3:continue
  ids=[i,*rng.choice(list(unique.values()),3,replace=False).tolist()]
  bank=target[ids]
  for name,v in vectors.items():
   scores=bank@v[i];hits[name].append(bool(scores[0]>max(scores[1:])+1e-8))
 return {name:float(np.mean(v)) for name,v in hits.items()}|{'n':len(hits['eeg']),'correct':sum(hits['eeg']),'chance':.25,'chance_range':chance_range(len(hits['eeg']))} if hits['eeg'] else None

def fit_semantic(rows,root,look,encoder=encode):
 root=Path(root);phrases=phrase_examples(rows);kept=[];features=[];masks=[]
 for r in phrases:
  try:
   with np.load(root/r['context_file'],allow_pickle=False) as z:x,q=eeg_summary(z['sequence'],z['quality'],z['positions'])
   if not np.isfinite(x).all():continue
   features.append(x);masks.append(q);kept.append(r)
  except (OSError,ValueError,KeyError):continue
 phrases=kept;blocks=list(dict.fromkeys(r['block'] for r in phrases));report=dict(kind='semantic',ready=False,phrases=len(phrases),blocks=len(blocks),look=look,max_phrases=MAX_PHRASES,reason='Collecting free-writing phrases across 16 recording blocks; no repeated-word requirement.')
 if len(phrases)<32 or len(blocks)<16:return provisional(phrases,features,root,look,report,encoder)
 boundary_blocks=set(blocks[max(8,int(len(blocks)*.6)):]);cut=min(r['onset'] for r in phrases if r['block'] in boundary_blocks)
 train=[i for i,r in enumerate(phrases) if r['block'] not in boundary_blocks and r['end']<cut-60]
 # Exact phrase repeats are excluded from validation; evaluate generalization to new text.
 seen={phrases[i]['text'].casefold() for i in train};val=[i for i,r in enumerate(phrases) if r['block'] in boundary_blocks and r['text'].casefold() not in seen]
 if len(train)<16 or len(val)<16:return provisional(phrases,features,root,look,report,encoder)
 texts=[r['text'] for r in phrases];vectors=encoder(texts+[r['previous'] or ' ' for r in phrases]);y=vectors[:len(phrases)];previous=vectors[len(phrases):]
 x=np.asarray(features);q=np.asarray(masks);model=ridge(x[train],y[train]);pred=apply(model,x[val]);nuisance=apply(ridge(q[train],y[train]),q[val]);mean=unit(y[train].mean(0,keepdims=True))[0]
 score=(pred*y[val]).sum(1);base=(y[val]*mean).sum(1);history=(previous[val]*y[val]).sum(1);noise=(nuisance*y[val]).sum(1)
 gains=score-np.maximum.reduce([base,history,noise]);block_gains=[float(gains[[j for j,i in enumerate(val) if phrases[i]['block']==b]].mean()) for b in dict.fromkeys(phrases[i]['block'] for i in val)]
 wins=sum(g>0 for g in block_gains);n=len(block_gains);p=sum(math.comb(n,k) for k in range(wins,n+1))/2**n;alpha=.01/(look*(look+1));ready=n>=8 and np.mean(gains)>.02 and p<=alpha
 report['four_choice']=four_choice_scores(pred,y[val],{'typical':np.tile(mean,(len(val),1)),'text_history':previous[val],'signal_quality':nuisance},[phrases[i]['text'] for i in val])
 report.update(ready=bool(ready),training_phrases=len(train),validation_trials=len(val),validation_blocks=n,cosine=float(score.mean()),mean_baseline=float(base.mean()),text_history_baseline=float(history.mean()),mask_baseline=float(noise.mean()),gain=float(gains.mean()),p_block_sign=p,alpha=alpha,reason='Semantic retrieval passed later-block checks.' if ready else 'Semantic retrieval has not yet outperformed text-history and signal-quality baselines on later phrases.',peak_worker_MB=memory_check()/1e6)
 # Retrieval library contains only training phrases. The current phrase is never added as a candidate.
 bank_ids=list(dict.fromkeys(phrases[i]['text'] for i in train));bank_ids=[next(i for i in train if phrases[i]['text']==t) for t in bank_ids][-256:]
 target=root/'semantic_checkpoint.npz';tmp=root/'semantic_checkpoint.tmp.npz'
 np.savez_compressed(tmp,mean=model[0],scale=model[1],weights=model[2],bank=y[bank_ids],texts=np.array([phrases[i]['text'] for i in bank_ids]),ready=ready,look=look);os.replace(tmp,target)
 return str(target),report

if __name__=='__main__':
 request=Path(sys.argv[1]);body=json.loads(request.read_text());root=Path(body['root'])
 def watchdog():
  started=time.monotonic()
  while True:
   try:
    memory_check()
    if time.monotonic()-started>175:raise TimeoutError('Semantic worker reached its time budget; recording continues')
   except (MemoryError,TimeoutError) as e:
    (root/'semantic_result.json').write_text(json.dumps(dict(path=None,report=dict(kind='semantic',ready=False,reason=str(e)))))
    os._exit(0)
   time.sleep(.5)
 threading.Thread(target=watchdog,daemon=True).start()
 try:path,report=fit_semantic(body['rows'],root,body['look']);result=dict(path=path,report=report)
 except Exception as e:result=dict(path=None,report=dict(kind='semantic',ready=False,reason='Semantic training paused: '+str(e)))
 (root/'semantic_result.json').write_text(json.dumps(result))
