"""Local personal activities. No upload transport or text-based trait classifier."""
import json, os, time, uuid, random, gzip
from pathlib import Path
import numpy as np
from analysis import FS, CHANNELS, DEFAULT_THRESHOLDS, artifacts, spectrum
from private_storage import DATA_ROOT

IPIP_SOURCE='https://ipip.ori.org/newBigFive5broadKey.htm'
DOMAINS=[
 ('Extraversion',5,["Am the life of the party.","Feel comfortable around people.","Start conversations.","Talk to a lot of different people at parties.","Don't mind being the center of attention.","Don't talk a lot.","Keep in the background.","Have little to say.","Don't like to draw attention to myself.","Am quiet around strangers."]),
 ('Agreeableness',6,["Am interested in people.","Sympathize with others’ feelings.","Have a soft heart.","Take time out for others.","Feel others’ emotions.","Make people feel at ease.","Am not really interested in others.","Insult people.","Am not interested in other people's problems.","Feel little concern for others."]),
 ('Conscientiousness',6,["Am always prepared.","Pay attention to details.","Get chores done right away.","Like order.","Follow a schedule.","Am exacting in my work.","Leave my belongings around.","Make a mess of things.","Often forget to put things back in their proper place.","Shirk my duties."]),
 ('Emotional stability',2,["Am relaxed most of the time.","Seldom feel blue.","Get stressed out easily.","Worry about things.","Am easily disturbed.","Get upset easily.","Change my mood a lot.","Have frequent mood swings.","Get irritated easily.","Often feel blue."]),
 ('Intellect / imagination',7,["Have a rich vocabulary.","Have a vivid imagination.","Have excellent ideas.","Am quick to understand things.","Use difficult words.","Spend time reflecting on things.","Am full of ideas.","Have difficulty understanding abstract ideas.","Am not interested in abstract ideas.","Do not have a good imagination."])]
THEMES=[('Principles','Doing things correctly matters deeply to me.'),('Helping','I want to feel needed and appreciated.'),('Achievement','I want to succeed and be recognized.'),('Individuality','I want to express what makes me unique.'),('Understanding','I seek understanding and time to think.'),('Security','I look for reassurance and dependable support.'),('Possibility','I seek variety and new possibilities.'),('Autonomy','I want to protect my independence.'),('Harmony','I seek harmony and avoid conflict.')]

def questionnaire(kind):
 if kind=='enneagram':return [{'id':i,'text':q,'domain':name,'reverse':False} for i,(name,q) in enumerate(THEMES)]
 if kind not in ('extraversion','big5'):raise ValueError('Unknown questionnaire')
 return [dict(id=d*10+i,text=q,domain=name,reverse=i>=positive) for d,(name,positive,qs) in enumerate(DOMAINS) if kind=='big5' or d==0 for i,q in enumerate(qs)]

def score(kind,answers):
 items=questionnaire(kind)
 if not isinstance(answers,list) or len(answers)!=len(items) or any(type(x) is not int or not 1<=x<=5 for x in answers):raise ValueError('Answer every item from 1 to 5')
 groups={}
 for item,value in zip(items,answers):groups.setdefault(item['domain'],[]).append(6-value if item['reverse'] else value)
 return {k:round(float(np.mean(v)),2) for k,v in groups.items()}

class PersonalActivities:
 def __init__(self,root=None):
  self.root=Path(root or DATA_ROOT)/'personal';self.root.mkdir(mode=0o700,exist_ok=True,parents=True);self.current=None;self.last_sample=0
  active=self.root/'active.json'
  if active.exists():
   r=json.loads(active.read_text())
   if r.get('running'):
    self.current=r;self.finish('Interrupted when app closed')
 def write(self,path,value):
  temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,allow_nan=False));temp.chmod(0o600);os.replace(temp,path)
 def preferences(self):
  p=self.root/'preferences.json';return json.loads(p.read_text()) if p.exists() else dict(personalize=False,research_interest=False,version='personal-v1')
 def catalog(self):
  return dict(connected=self.connected(),preferences=self.preferences(),questionnaires={k:questionnaire(k) for k in ['extraversion','big5','enneagram']},history=self.history(),running=self.current is not None)
 def connected(self):
  if not self.preferences().get('personalize'):return {'enabled':False}
  history=self.history()
  typing=self.root.parent/'typing'
  return dict(enabled=True,questionnaires=sum('scores' in r for r in history),eeg_sessions=sum('summary' in r for r in history),writing_sessions=sum(p.is_dir() for p in typing.iterdir()) if typing.exists() else 0,model_status='No validated cross-activity personality predictor is available. These records are available for future local personalization.')
 def history(self):
  result=[]
  for p in sorted(self.root.glob('record-*.json'),reverse=True)[:60]:
   r=json.loads(p.read_text());result.append({k:v for k,v in r.items() if k not in ('answers','clips')})
  return result
 def request(self,action,body,engine):
  if action in ('context','context-link'):
   from participant_context import participant_context
   return participant_context(self.root.parent,action,body,engine)
  if action=='catalog':return self.catalog()
  if action=='preferences':
   if body.get('version')!='personal-v1':raise ValueError('Review the current connected-data explanation')
   prefs=dict(version='personal-v1',personalize=body.get('personalize') is True,research_interest=body.get('research_interest') is True,updated_at=time.time())
   self.write(self.root/'preferences.json',prefs);return prefs
  if action=='questionnaire-event':
   r=self.current
   if not r or r['kind'] not in ('extraversion','big5','enneagram'):raise ValueError('Start questionnaire EEG recording first')
   index=body.get('index');value=body.get('value');items=questionnaire(r['kind'])
   if type(index) is not int or not 0<=index<len(items):raise ValueError('Invalid question')
   if value is not None and (type(value) is not int or not 1<=value<=5):raise ValueError('Invalid answer')
   r.setdefault('answer_events',[]).append(dict(time=time.time(),index=index,value=value))
   if value is not None:r['answers'][index]=value
   self.write(self.root/'active.json',r);return {'saved':True}
  if action=='questionnaire':
   if not self.current:raise ValueError('EEG recording stopped; start the questionnaire again')
   if not engine.times or time.time()-engine.times[-1]>1:raise ValueError('EEG signal lost; reconnect before completing')
   if self.current['kind']!=body.get('kind'):raise ValueError('Questionnaire does not match recording')
   self.current.update(scores=score(body['kind'],body['answers']),answers=body['answers'],measure='self-report with concurrent EEG')
   result=self.current;self.finish('Completed');return result
  if action=='start':
   if self.current or engine.typing.running or engine.developer.current is not None or engine.session and engine.session.get('running'):raise ValueError('Finish the current recording first')
   if not engine.times or time.time()-engine.times[-1]>1:raise ValueError('Connect the headset and wait for live EEG')
   kind=body.get('kind')
   plans={'social_probe':[('Browse messages',60),('Send a message',60)],'reset':[('Baseline',30),('Breathing',45),('Baseline',30),('Quiet attention',45),('Baseline',30),('Gratitude',45)],'meditation':[('Baseline',30),('Meditation',120)],'eeg_profile':[('Eyes-open rest',60)]}
   for name in ('extraversion','big5','enneagram'):plans[name]=[('Questionnaire',1800)]
   if kind not in plans:raise ValueError('Unknown activity')
   if kind=='reset':
    activities=['Breathing','Quiet attention','Gratitude'];random.SystemRandom().shuffle(activities);plans[kind]=[phase for activity in activities for phase in [('Baseline',30),(activity,45)]]
   self.current=dict(id=uuid.uuid4().hex,kind=kind,created=time.time(),source=engine.source,plan=plans[kind],clips=[],ratings={},running=True);self.current['raw_eeg_file']=self.current['id']+'-eeg.jsonl.gz';self.current['schema_version']=2;self.current['montage']={'channels':list(CHANNELS),'reference':'Fpz','sample_rate':FS};self.current['related_activity']=body.get('related_activity') if isinstance(body.get('related_activity'),str) else None;self.current['answers']=[None]*len(questionnaire(kind)) if kind in ('extraversion','big5','enneagram') else [];self.last_sample=time.time();self.write(self.root/'active.json',self.current);return self.status()
  if action=='status':return self.status()
  if action=='stop':
   if self.current:self.finish('Stopped early')
   return self.status()
  if action=='reflection':
   ident=body.get('id');values={k:body.get(k) for k in ('effort','social_ease')}
   if any(type(v) is not int or not 1<=v<=5 for v in values.values()):raise ValueError('Choose ratings from 1 to 5')
   for p in self.root.glob('record-*.json'):
    r=json.loads(p.read_text())
    if r.get('id')==ident:r['reflection']=values;self.write(p,r);return {'saved':True}
   raise ValueError('Activity not found')
  if action=='rate':
   rating=body.get('rating');ident=body.get('id')
   if type(rating) is not int or not 1<=rating<=5:raise ValueError('Choose a rating from 1 to 5')
   for p in self.root.glob('record-*.json'):
    r=json.loads(p.read_text())
    if r.get('id')==ident:r['helpfulness']=rating;self.write(p,r);return {'saved':True}
   raise ValueError('Activity not found')
  raise ValueError('Unknown personal action')
 def record_raw(self,times,values):
  if not self.current:return
  name=self.current['id']+'-eeg.jsonl.gz';self.current['raw_eeg_file']=name
  with gzip.open(self.root/name,'at') as f:
   for t,row in zip(times,values):
    f.write(json.dumps({'time':float(t),'uv':[float(v) if np.isfinite(v) else None for v in row]},allow_nan=False)+'\n')
 def ingest(self,times,raw,filtered):
  if not self.current:return
  t=np.asarray(times);end=float(t[-1]);elapsed=end-self.current['created'];total=sum(v for _,v in self.current['plan'])
  if elapsed>=total:self.finish('Completed');return
  if end-self.last_sample<2:return
  self.last_sample=end;ids=np.flatnonzero(t>end-2)
  if len(ids)<FS*2-2:return
  phase,start=self.phase(elapsed);power={};reasons={}
  for ch,name in enumerate(CHANNELS):
   why=artifacts(np.asarray(raw)[ids],t[ids],DEFAULT_THRESHOLDS,[ch]);x=np.asarray(filtered)[ids,ch]
   if not np.isfinite(x).all():why.append('Missing signal')
   if elapsed-start<4:why.append('Transition')
   reasons[name]=why
   if not why:
    f,p=spectrum(x[:,None]);power[name]=[float(10*np.log10(max(np.sum(p[(f>=lo)&(f<hi),0])*(f[1]-f[0]),1e-12))) for lo,hi in [(4,8),(8,13),(13,20),(20,30)]]
  self.current['clips'].append(dict(time=end,phase=phase,phase_start=start,power=power,reasons=reasons))
  # Autosave every clip; interrupted sessions remain available locally.
  self.write(self.root/('active.json'),self.current)
 def phase(self,elapsed):
  start=0
  for name,duration in self.current['plan']:
   if elapsed<start+duration:return name,start
   start+=duration
  return 'Complete',start
 def summarize(self,r):
  phases={}
  for name,_ in r['plan']:
   if name in phases:continue
   phases[name]={}
   for ch in CHANNELS:
    values=[c['power'][ch] for c in r['clips'] if c['phase']==name and ch in c['power']]
    phases[name][ch]=dict(n=len(values),db=np.mean(values,axis=0).tolist() if values else None)
  ranking=[]
  # Compare each activity with its immediately preceding baseline, channel by channel.
  start=0;baseline_start=None
  for name,duration in r['plan']:
   if name=='Baseline':baseline_start=start
   elif baseline_start is not None:
    differences=[]
    for ch in CHANNELS:
     a=[c['power'][ch] for c in r['clips'] if c['phase_start']==baseline_start and ch in c['power']]
     b=[c['power'][ch] for c in r['clips'] if c['phase_start']==start and ch in c['power']]
     if len(a)>=5 and len(b)>=5:differences.append(float(np.mean(np.abs(np.mean(b,axis=0)-np.mean(a,axis=0)))))
    ranking.append(dict(activity=name,change_db=float(np.mean(differences)) if differences else None,channels=len(differences)))
   start+=duration
  ranking.sort(key=lambda x:x['change_db'] if x['change_db'] is not None else -1,reverse=True)
  return dict(hypothesis=self.hypothesis(phases,r['kind']),phases=phases,ranking=ranking,clean_clips=sum(bool(c['power']) for c in r['clips']),total_clips=len(r['clips']))
 def hypothesis(self,phases,kind):
  if kind!='social_probe':return None
  changes=[]
  for ch in ('AF7','AF8'):
   a=phases.get('Browse messages',{}).get(ch,{});b=phases.get('Send a message',{}).get(ch,{})
   if a.get('n',0)>=10 and b.get('n',0)>=10:changes.append(b['db'][0]-a['db'][0])
  if len(changes)!=2:return {'text':'Not enough clean frontal EEG for a tentative comparison.','basis':'At least 10 usable clips per frontal channel in each step.'}
  delta=float(np.mean(changes))
  text='No consistent directional frontal-theta change; psychological interpretation is inconclusive.'
  if all(x>0.5 for x in changes):text='Ultra-tentative: composing the message may have required more mental effort than browsing.'
  elif all(x<-.5 for x in changes):text='Ultra-tentative: composing the message may have required less mental effort than browsing.'
  return {'text':text,'theta_change_db':delta,'basis':'Frontal-theta workload research motivates this hypothesis. The ±0.5 dB concordance rule is an unvalidated display heuristic, not a significance threshold. AF7/AF8 differ from frontal-midline research electrodes. Eye movements, typing, message content and task order can explain changes. This cannot establish introversion/extraversion.','source':'https://pubmed.ncbi.nlm.nih.gov/35128686/'}
 def status(self):
  if self.current and time.time()-self.last_sample>5:self.finish('Signal lost; partial recording saved')
  if not self.current:return {'running':False,'history':self.history()}
  elapsed=max(0,time.time()-self.current['created']);phase,start=self.phase(elapsed)
  return dict(recent_clips=self.current['clips'][-30:],running=True,id=self.current['id'],kind=self.current['kind'],source=self.current['source'],elapsed=elapsed,remaining=max(0,sum(v for _,v in self.current['plan'])-elapsed),phase=phase,answers=self.current.get('answers',[]),phase_elapsed=elapsed-start,phase_remaining=max(0,next((duration for name,duration in self.current['plan'] if name==phase),0)-(elapsed-start)),summary=self.summarize(self.current))
 def finish(self,reason):
  r=self.current;r.update(running=False,ended=time.time(),reason=reason,summary=self.summarize(r));self.write(self.root/('record-'+str(time.time_ns())+'.json'),r);self.write(self.root/'active.json',{'running':False});self.current=None
