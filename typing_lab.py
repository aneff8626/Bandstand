"""Local free-writing EEG collection and conservative closed-vocabulary decoding.
Text supplies labels only. Predictor inputs contain only EEG-derived features.
"""
import csv,json,time,uuid,threading,math,re,gzip,shutil,subprocess,sys,os
from pathlib import Path
from collections import deque,Counter
import numpy as np
from analysis import FS,CHANNELS,artifacts,DEFAULT_THRESHOLDS
from sequence_decoder import context_tokens,channel_quality,fit_context
from semantic_decoder import SemanticModel,phrase_examples,MAX_WORDS

def read_lines(path):
 with path.open() as handle:yield from handle

WINDOWS={'pre':(-1.,0.),'post':(0.,1.)}

def word_label(text):
 return re.sub(r"^[^\w]+|[^\w]+$",'',str(text).lower()).strip('_')[:80]

def eeg_features(x):
 """118 features: time course, time-local band power, log spatial covariance, slope."""
 x=np.asarray(x,float)
 if x.shape!=(FS,4) or not np.isfinite(x).all():raise ValueError('A complete 1-second EEG epoch is required')
 x=x-x.mean(0)
 temporal=np.array_split(x,16);parts=[np.concatenate([v.mean(0) for v in temporal])]
 for half in np.array_split(x,2):
  n=len(half);w=np.hanning(n);f=np.fft.rfftfreq(n,1/FS)
  p=abs(np.fft.rfft(half*w[:,None],axis=0))**2/(FS*np.sum(w*w))
  for lo,hi in [(2,4),(4,8),(8,13),(13,20),(20,30)]:parts.append(np.log1p(p[(f>=lo)&(f<hi)].sum(0)*FS/n))
 cov=x.T@x/(len(x)-1);cov=.9*cov+.1*np.eye(4)*max(np.trace(cov)/4,1e-6)
 eig,u=np.linalg.eigh(cov);logcov=(u*np.log(np.maximum(eig,1e-6)))@u.T
 parts.append(logcov[np.triu_indices(4)]);parts.append(x[-32:].mean(0)-x[:32].mean(0))
 return np.concatenate(parts)

def fit_ridge(x,labels,classes):
 x=np.asarray(x);mean=x.mean(0);scale=np.maximum(x.std(0),1e-5);z=np.clip((x-mean)/scale,-8,8)
 counts=Counter(labels);weights=np.array([1/counts[y] for y in labels]);weights*=len(weights)/sum(weights)
 y=np.array([[float(label==c) for c in classes] for label in labels]);z=np.c_[np.ones(len(z)),z]
 penalty=np.eye(z.shape[1])*10;penalty[0,0]=1e-6
 coef=np.linalg.solve(z.T@(weights[:,None]*z)+penalty,z.T@(weights[:,None]*y))
 return dict(mean=mean.tolist(),scale=scale.tolist(),coef=coef.tolist(),classes=classes)

def predict(model,x):
 z=np.clip((np.asarray(x)-model['mean'])/model['scale'],-8,8)
 scores=np.r_[1,z]@np.asarray(model['coef']);idx=np.argsort(scores)
 return model['classes'][idx[-1]],float(scores[idx[-1]]-scores[idx[-2]])

def evaluate(rows,window,look):
 rows=sorted([r for r in rows if r.get('accepted',{}).get(window) and r.get('label')],key=lambda r:r['onset'])
 blocks=list(dict.fromkeys(r['block'] for r in rows))
 status=dict(ready=False,reason='Collect at least 8 training and 8 later validation blocks (one minute each).',window=window,look=look,blocks=len(blocks))
 if len(blocks)<16:return None,status
 split=max(8,int(len(blocks)*.65));split=min(split,len(blocks)-8);training=set(blocks[:split]);validation=set(blocks[split:])
 boundary=min(r['onset'] for r in rows if r['block'] in validation)
 train=[r for r in rows if r['block'] in training and r['onset']+1<boundary-1.5]
 counts=Counter(r['label'] for r in train);classes=[w for w,n in counts.most_common(12) if n>=30]
 if len(classes)<2:status['reason']='Need at least 30 clean training examples of each of two recurring words.';return None,status
 train=[r for r in train if r['label'] in classes];val=[r for r in rows if r['block'] in validation and r['label'] in classes]
 vc=Counter(r['label'] for r in val)
 status.update(classes=classes,training_counts=dict(Counter(r['label'] for r in train)),validation_counts=dict(vc),validation_blocks=len(set(r['block'] for r in val)))
 if any(vc[c]<10 for c in classes):status['reason']='Need at least 10 later validation examples for every candidate word.';return None,status
 model=fit_ridge([r['features'][window] for r in train],[r['label'] for r in train],classes)
 predictions=[predict(model,r['features'][window])[0] for r in val];correct=np.array([p==r['label'] for p,r in zip(predictions,val)])
 majority=Counter(r['label'] for r in train).most_common(1)[0][0];chance=1/len(classes)
 acc=float(correct.mean());balanced=float(np.mean([correct[np.array([r['label']==c for r in val])].mean() for c in classes]))
 deltas=[]
 for block in dict.fromkeys(r['block'] for r in val):
  ids=[i for i,r in enumerate(val) if r['block']==block]
  if len(ids)<3:continue
  base=max(chance,np.mean([val[i]['label']==majority for i in ids]));deltas.append(float(correct[ids].mean()-base))
 wins=sum(d>0 for d in deltas);n=sum(d!=0 for d in deltas)
 p=sum(math.comb(n,k) for k in range(wins,n+1))/2**n if n else 1
 alpha=.01/(look*(look+1))
 ready=len(deltas)>=8 and acc>=.6 and balanced>=chance+.1 and p<=alpha
 status.update(ready=ready,accuracy=acc,balanced_accuracy=balanced,chance=chance,majority_accuracy=float(np.mean([r['label']==majority for r in val])),validation_trials=len(val),block_wins=wins,scored_blocks=len(deltas),p_block_sign=p,alpha=alpha,reason='Exploratory decoder passed later-block checks.' if ready else 'Later-block performance is not yet reliable enough to display predictions.',limitations='Within-writer EEG classification; motor, eye and muscle activity may contribute. This is not validated thought or language decoding.')
 return model if ready else None,status

class TypingLab:
 def __init__(self,root,data_dir=None):
  self.root=(Path(data_dir) if data_dir is not None else Path(root)/'data')/'typing';self.root.mkdir(parents=True,exist_ok=True)
  self.running=False;self.session=None;self.pending={};self.history=[];self.word_onsets=[];self.rows=deque(maxlen=MAX_WORDS);self.lock=threading.RLock();self.models={};self.reports={w:dict(ready=False,reason='Collecting clean examples of recurring words.') for w in WINDOWS};self.prediction=None;self.revision=0;self.last_fit=0;self.fitting=False;self.look=0;self.last_epoch=None;self.sequence_model=None;self.native_word=None;self.native_boundary=False;self.native_app=None;self.capture_status={};self.focus_id=uuid.uuid4().hex;self.last_semantic_fit=0;self.last_disk_check=0;self.last_live_prediction=0;self.total_words=0;self.recording_sessions={};self.session_last_word={}
  for p in sorted(self.root.glob('*/trials.jsonl')):
   for line in read_lines(p):
    try:
     row=json.loads(line);self.rows.append(row);self.count_word(row)
    except (ValueError,TypeError):pass
  for path in self.root.glob('*/session.json'):
   try:
    saved=json.loads(path.read_text());self.recording_sessions[saved['id']]=saved
   except (ValueError,KeyError):pass
  self.reports['context']=dict(ready=False,reason='Collecting free-writing phrases for semantic retrieval.')
  replacements={};recent_ids={(r.get("session"),r.get("id")) for r in self.rows}
  for p in sorted(self.root.glob('*/context_trials.jsonl')):
   for line in read_lines(p):
    try:
     row=json.loads(line);key=(row['session'],row['id']);
     if key in recent_ids:replacements[key]=row
    except (ValueError,KeyError):pass
  self.rows=deque((replacements.get((r.get('session'),r.get('id')),r) for r in self.rows),maxlen=MAX_WORDS)
  audit=self.root/'semantic_evaluation_count.json'
  if audit.exists():
   try:self.look=int(json.loads(audit.read_text())['looks'])
   except (ValueError,KeyError):pass
 def count_word(self,row):
  if row.get('label') and not row.get('cancelled') and not row.get('incomplete'):self.total_words+=1
  ident=row.get('session');self.session_last_word[ident]=max(self.session_last_word.get(ident,0),row.get('committed',row.get('onset',0)))
 def recording_minutes(self):
  total=0
  for ident,s in self.recording_sessions.items():
   start=s.get('started',0);last=self.session_last_word.get(ident,start)
   end=time.time() if self.running and self.session and ident==self.session['id'] else (s.get('ended') or last)
   if not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or not math.isfinite(start+end):continue
   # Corrupt/mixed-clock stop times must not produce decades of recording.
   if end-start>7*86400:end=last
   total+=max(0,end-start) if math.isfinite(end) and end-start<=7*86400 else 0
  return total/60
 def start(self,window='context',history=30,delay=0,capture='editor'):
  if self.running:raise ValueError('Typing is already recording')
  if window not in [*WINDOWS,'context']:raise ValueError('Unknown EEG window')
  if history not in [10,30,60] or delay not in [0,1] or capture not in ['editor','system']:raise ValueError('Invalid context/capture settings')
  self.native_word=None;self.native_boundary=False;self.native_app=None
  now=time.time();ident=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6];self.directory=self.root/ident;self.directory.mkdir()
  self.session=dict(id=ident,started=now,window=window,history_seconds=history,prediction_delay=delay,capture=capture,source='live',sample_rate=FS,channels=CHANNELS,epoch=[-1.5,1.],baseline=[-1.5,-1.25],timing='Browser beforeinput timestamp; BLE and physical key onset uncalibrated',model_features='EEG only; text and edit timings are labels/quality checks, never predictors')
  self.recording_sessions[ident]=self.session
  self.running=True;self.pending={};self.history=[];self.word_onsets=[];self.prediction=None
  self.rawfile=gzip.open(self.directory/'continuous.csv.gz','wt',newline='',compresslevel=1);self.writer=csv.writer(self.rawfile);self.writer.writerow(['time',*CHANNELS,*[c+'_filtered' for c in CHANNELS]])
  self.eventfile=open(self.directory/'events.jsonl','a');self.trialfile=open(self.directory/'trials.jsonl','a');self._save_session();self.maybe_fit();return self.status()
 def _save_session(self):
  (self.directory/'session.json').write_text(json.dumps(self.session,indent=2))
 def event(self,body,times,raw,filtered):
  if not self.running:raise ValueError('Start typing recording first')
  kind=body.get('kind');onset=float(body.get('onset',time.time()))
  if not math.isfinite(onset) or abs(onset-time.time())>10:raise ValueError('Typing timestamp outside synchronized clock range')
  e={**body,'received_at':time.time()};self.eventfile.write(json.dumps(e)+'\n');self.eventfile.flush()
  if kind=='document':(self.directory/'document.txt').write_text(str(body.get('text','')))
  elif kind=='onset':
   ident=str(body['id']);
   if not re.fullmatch(r'[a-zA-Z0-9-]{1,80}',ident):raise ValueError('Invalid word marker')
   self.pending[ident]=dict(id=ident,onset=onset,label=None,typed='',edits=[],session=self.session['id'],block=self.session['id']+':'+str(int((onset-self.session['started'])//60)),context_block=self.session['id']+':'+str(int((onset-self.session['started'])//120)),focus_id=self.focus_id,accepted={},reasons={},features={},prediction=None)
   self.word_onsets.append(onset);self.word_onsets=self.word_onsets[-300:]
   # Keep the previous semantic match visible until the next estimate arrives.
  elif kind=='edit':
   self.history.append(onset);self.history=self.history[-2000:]
  elif kind in ('commit','cancel'):
   trial=self.pending.get(str(body.get('id')))
   if trial:
    trial.update(typed=str(body.get('text','')),label=word_label(body.get('text','')) if kind=='commit' else '',committed=onset,cancelled=kind=='cancel',edited=bool(body.get('edited')),unsupported=bool(body.get('unsupported')))
  self.process(times,raw,filtered);return self.status()
 def native_event(self,body,times,raw,filtered):
  if not self.running or self.session.get('capture')!='system':return {}
  kind=body.get('kind');now=float(body.get('onset',time.time()))
  if kind=='status':self.capture_status=body;return {}
  if kind=='boundary' or (self.native_app is not None and self.native_app!=body.get('app')):
   if self.native_word:self.event(dict(kind='cancel',id=self.native_word['id'],onset=now,text=self.native_word['text'],unsupported=True),times,raw,filtered)
   self.native_word=None;self.native_boundary=False;self.focus_id=uuid.uuid4().hex
   if kind=='boundary':return {}
  self.native_app=body.get('app')
  if kind!='key':return {}
  chars=body.get('text','');code=body.get('keycode')
  if body.get('shortcut') or code in [48,53,115,116,117,119,121,123,124,125,126]:
   return self.native_event(dict(kind='boundary',onset=now),times,raw,filtered)
  self.event(dict(kind='edit',onset=now,input_type='nativeKey',data=chars,keycode=code,app=self.native_app),times,raw,filtered)
  if code==51:
   if self.native_word:
    self.native_word['text']=self.native_word['text'][:-1];self.native_word['edited']=True
    if not self.native_word['text']:
     self.event(dict(kind='cancel',onset=now,id=self.native_word['id'],text=''),times,raw,filtered);self.native_word=None
   else:self.native_boundary=False
   return {}
  if chars.isspace() or code in [36,76]:
   if self.native_word:self.event(dict(kind='commit',onset=now,**self.native_word),times,raw,filtered)
   self.native_word=None;self.native_boundary=True;return {}
  if len(chars)!=1 or not chars.isprintable():return self.native_event(dict(kind='boundary',onset=now),times,raw,filtered)
  if not self.native_word:
   if not self.native_boundary:return {}
   self.native_word=dict(id='native-'+uuid.uuid4().hex,text='',edited=False)
   self.event(dict(kind='onset',id=self.native_word['id'],onset=now,app=self.native_app),times,raw,filtered)
  self.native_word['text']+=chars
  return {}
 def ingest(self,times,raw,filtered):
  if not self.running:return
  if time.time()-self.last_disk_check>10:
   self.last_disk_check=time.time()
   if shutil.disk_usage(self.root).free<10*1024**3:
    self.stop('Low disk space: recording stopped with less than 10 GiB free');return
  for t,r,f in zip(times,raw,filtered):self.writer.writerow([float(t),*r,*f])
  self.rawfile.flush()
 def process(self,times,raw,filtered):
  if not self.running or not len(times):return
  t=np.asarray(times);x=np.asarray(raw);f=np.asarray(filtered)
  for ident,trial in list(self.pending.items()):
   onset=trial['onset'];selected=self.session['window']
   for window,(lo,hi) in WINDOWS.items():
    if window in trial['accepted'] or t[-1]<onset+hi+.04:continue
    ids=np.flatnonzero((t>=onset+lo)&(t<onset+hi));reasons=[]
    if len(ids)<FS-2 or (len(ids) and (t[ids[0]]>onset+lo+2/FS or t[ids[-1]]<onset+hi-2/FS)):reasons=['Incomplete EEG window']
    elif len(ids):
     quality,channel_reasons=channel_quality(x[ids],t[ids]);good_channels=np.mean(quality,axis=0)>=.4
     trial.setdefault('channel_quality',{})[window]={'usable_channels':[CHANNELS[i] for i in np.flatnonzero(good_channels)],'reasons':channel_reasons}
     if good_channels.sum()<2:reasons=['Insufficient usable EEG on two channels']
    trial['overlapping_typing']=any(onset-1<k<onset-.05 for k in self.history) or any(onset<k<onset+1 for k in self.word_onsets)
    trial['accepted'][window]=not reasons;trial['reasons'][window]=reasons
    if not reasons:
     grid=onset+lo+np.arange(FS)/FS;epoch=np.stack([np.interp(grid,t[ids],np.nan_to_num(f[ids,i])) if good_channels[i] else np.zeros(FS) for i in range(4)],axis=1);trial['features'][window]=eeg_features(epoch).tolist()
     model=self.models.get(window)
     if model and window==selected:
      word,margin=predict(model,trial['features'][window]);in_distribution=float(np.mean(np.abs((np.asarray(trial['features'][window])-model['mean'])/model['scale'])>4))<.1;trial['prediction']=dict(word=word if margin>=.15 and in_distribution else None,reason='EEG estimate · exploratory' if margin>=.15 and in_distribution else 'EEG estimate is ambiguous',margin=margin,model_look=self.reports[window].get('look'),generated_at=time.time(),trial=ident)
      self.prediction=trial['prediction']
    if window==selected and (reasons or not self.models.get(window)):self.prediction=dict(word=None,reason='Artifact / overlapping typing: no prediction' if reasons else self.reports[window]['reason'],trial=ident)
   delay=self.session.get('prediction_delay',0)
   if 'context' not in trial['accepted'] and t[-1]>=onset+delay+.04:
    seq,q,pos,quality=context_tokens(t,x,f,onset,self.session.get('history_seconds',30),delay)
    trial['accepted']['context']=quality['usable'];trial['context_quality']=quality;trial['reasons']['context']=[] if quality['usable'] else [quality['reason']]
    trial['context_file']=self.session['id']+'/'+ident+'.context.npz'
    np.savez_compressed(self.root/trial['context_file'],sequence=seq,quality=q,positions=pos)
    if self.sequence_model and quality['usable']:
     result=self.sequence_model.predict(seq,q,pos);result.update(trial=ident,generated_at=time.time());trial['prediction']=result;self.prediction=result
    elif selected=='context':self.prediction=dict(word=None,reason=self.reports['context']['reason'] if quality['usable'] else quality['reason'],trial=ident)
   if t[-1]>=onset+1.05 and 'committed' in trial:
    ep=np.flatnonzero((t>=onset-1.5)&(t<onset+1));base=np.flatnonzero((t>=onset-1.5)&(t<onset-1.25))
    wave=f[ep]-np.mean(f[base],axis=0) if len(base) else f[ep]
    np.savez_compressed(self.directory/(ident+'.npz'),times=t[ep]-onset,raw=x[ep],filtered=f[ep],baseline_corrected=wave)
    if trial.get('cancelled') or trial.get('unsupported') or not trial.get('label'):
     for w in [*WINDOWS,'context']:trial['accepted'][w]=False;trial['reasons'].setdefault(w,[]).append('Unlabeled or unsupported edit')
    eq,_=channel_quality(x[ep],t[ep]) if len(ep) else (np.zeros((1,4)),{})
    trial['erp_channel_accepted']=(np.mean(eq,axis=0)>=.7).tolist();trial['erp_accepted']=len(base)>=62 and len(ep)>=638 and sum(trial['erp_channel_accepted'])>=2
    for ch,ok in enumerate(trial['erp_channel_accepted']):
     if not ok:wave[:,ch]=np.nan
    trial['erp_times']=(t[ep]-onset)[::4].tolist();trial['erp_values']=[[float(v) if np.isfinite(v) else None for v in row] for row in wave[::4]];
    self.rows.append(trial);self.count_word(trial);self.trialfile.write(json.dumps(trial)+'\n');self.trialfile.flush();self.last_epoch=dict(times=(t[ep]-onset)[::4].tolist(),values=[[float(v) if np.isfinite(v) else None for v in row] for row in wave[::4]],label=trial['typed'],accepted=trial['accepted']);del self.pending[ident];self.revision+=1
  self.maybe_fit()
 def live_predict(self,times,raw,filtered):
  if not self.running or not self.sequence_model or not len(times) or time.time()-self.last_live_prediction<1:return
  self.last_live_prediction=time.time()
  seq,q,pos,quality=context_tokens(times,raw,filtered,float(times[-1])+.0001,self.session.get('history_seconds',30),0)
  if quality['usable']:
   result=self.sequence_model.predict(seq,q,pos);result.update(generated_at=time.time(),live=True,eeg_cutoff=float(times[-1]));self.prediction=result
  else:self.prediction=dict(word=None,candidates=[],reason='Waiting for usable EEG to refresh the tentative match',generated_at=time.time(),live=True)

 def maybe_fit(self):
  if self.fitting or len(self.rows)<100 or (len(self.rows)-self.last_fit<100 and len(self.rows)<MAX_WORDS) or time.time()-self.last_semantic_fit<300:return
  self.last_fit=len(self.rows);self.last_semantic_fit=time.time();self.fitting=True;self.look+=1;look=self.look
  rows=[{k:r[k] for k in ('id','onset','committed','session','typed','label','context_block','context_file','accepted','cancelled','unsupported','incomplete','focus_id') if k in r} for r in self.rows]
  (self.root/'semantic_evaluation_count.json').write_text(json.dumps({'looks':look}))
  request=self.root/'semantic_request.json';request.write_text(json.dumps(dict(root=str(self.root.resolve()),look=look,rows=rows)))
  def worker():
   try:
    result=self.root/'semantic_result.json'
    if result.exists():result.unlink()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    subprocess.run([sys.executable,str(Path(__file__).with_name('semantic_decoder.py')),str(request)],check=True,timeout=180,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    output=json.loads(result.read_text());model=SemanticModel(output['path']) if output.get('path') else None
    with self.lock:
     self.sequence_model=model;self.reports['context']=output['report']
     (self.root/'decoder_review.json').write_text(json.dumps(self.reports,indent=2))
   except Exception as e:self.reports['context']=dict(kind='semantic',ready=False,reason='Semantic training paused: '+str(e));self.sequence_model=None
   finally:self.fitting=False
  threading.Thread(target=worker,daemon=True).start()
 def stop(self,reason='Stopped'):
  if not self.running:return self.status()
  for trial in self.pending.values():
   trial.update(incomplete=True,stop_reason=reason);trial['accepted']={w:False for w in [*WINDOWS,'context']};trial['reasons']={w:['Recording stopped before full epoch was saved'] for w in [*WINDOWS,'context']};self.rows.append(trial);self.count_word(trial);self.trialfile.write(json.dumps(trial)+'\n')
  self.pending={};self.running=False;self.session.update(ended=time.time(),stop_reason=reason);self._save_session()
  for f in (self.rawfile,self.eventfile,self.trialfile):f.close()
  return self.status()
 def status(self):
  w=self.session['window'] if self.session else 'context';counts=Counter(r.get('label') for r in self.rows if r.get('accepted',{}).get(w) and r.get('label'));rejected=sum(not r.get('accepted',{}).get(w) for r in self.rows)
  matches=[r for r in self.rows if self.last_epoch and r.get('typed')==self.last_epoch['label'] and r.get('accepted',{}).get(w) and r.get('erp_accepted') and len(r.get('erp_values',[]))==160]
  erp=None
  if matches:
   waves=np.asarray([r['erp_values'] for r in matches],float);valid=np.isfinite(waves);mean=np.nansum(waves,axis=0)/np.maximum(valid.sum(0),1);mean[valid.sum(0)==0]=np.nan;erp=dict(n=len(waves),times=matches[-1]['erp_times'],mean=[[float(v) if np.isfinite(v) else None for v in row] for row in mean])
  semantic=phrase_examples(self.rows)
  return dict(lifetime_words=self.total_words,session_count=len(self.recording_sessions),recording_minutes=self.recording_minutes(),semantic_blocks=len(set(r['block'] for r in semantic)),semantic_phrases=len(semantic),dataset_scope='Most recent '+str(MAX_WORDS)+' words in memory; all recordings remain on disk',resource_policy='Compressed EEG · 512 phrases/fit · one CPU thread · 180-second worker limit · 10 GiB disk reserve',capture_status=self.capture_status,erp=erp,running=self.running,session=self.session,counts=dict(counts.most_common(20)),total=len(self.rows),accepted=sum(counts.values()),rejected=rejected,pending=len(self.pending),prediction=self.prediction,decoder=self.reports[w],fitting=self.fitting,last_epoch=self.last_epoch,revision=self.revision)
