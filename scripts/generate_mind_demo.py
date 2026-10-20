"""Generate synthetic UI fixtures only; never fit or upload them as participant data."""
import random,json,math
from pathlib import Path
import sys,os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from personal import DOMAINS,THEMES
rng=random.Random(20261016)
data={'schema':1,'synthetic':True,'purpose':'UI demonstration only; invented participants and EEG, no validated EEG-personality relationship','seed':20261016,'datasets':{}}
for kind,names in [('big5',[d[0] for d in DOMAINS]),('enneagram',[d[0] for d in THEMES])]:
 rows=[]
 for i in range(120):
  scores={n:round(min(5,max(1,rng.gauss(3,.85))),2) for n in names}
  freqs=[1+j*.5 for j in range(79)]
  spectra=[]
  for ch in range(4):
   alpha=rng.uniform(5,22);beta=rng.uniform(1,6)
   spectra.append([round(4/(f**1.3)+alpha*math.exp(-.5*((f-10)/1.3)**2)+beta*math.exp(-.5*((f-19)/3)**2)+rng.random()*.15,4) for f in freqs])
  rows.append({'id':f'synthetic-{kind}-{i+1:03}', 'scores':scores,'psd':spectra})
 data['datasets'][kind]={'domains':names,'frequencies':freqs,'participants':rows}
Path('assets/demo/mind-reference.json').write_text(json.dumps(data,separators=(',',':')))
Path('web/mind-demo.js').write_text('/* Synthetic UI fixtures only. Never training or participant records. */\nconst mindDemoData='+json.dumps(data,separators=(',',':'))+';\n')

# Separate demo database: shared subject IDs, actual scored synthetic answers,
# invented EEG summaries, and explicit provenance on every record.
from personal import questionnaire,score
records=[]
for i in range(100):
 for kind in ('big5','enneagram'):
  answers=[rng.randint(1,5) for _ in questionnaire(kind)]
  profile=data['datasets'][kind]['participants'][i]
  frequencies=data['datasets'][kind]['frequencies']
  channels={}
  for ch,psd in zip(('TP9','AF7','AF8','TP10'),profile['psd']):
   channels[ch]={'n':60,'db':[10*math.log10(sum(p*.5 for f,p in zip(frequencies,psd) if lo<=f<hi)) for lo,hi in ((4,8),(8,13),(13,20),(20,30))]}
  created=1790812800+i*3600+(600 if kind=='enneagram' else 0)
  records.append(dict(id=f'demo-{kind}-{i+1:03}',subject_id=f'Demo subject {i+1:03}',kind=kind,created=created,ended=created+120,source='synthetic-database',synthetic=True,provenance='Invented answers and EEG; no real participant. Excluded from training and upload.',answers=answers,scores=score(kind,answers),summary={'clean_clips':60,'total_clips':60,'phases':{'Questionnaire':channels}},psd=profile['psd']))
database={'schema':1,'synthetic':True,'subjects':100,'records':records}
Path('assets/demo/subject-database.json').write_text(json.dumps(database,separators=(',',':')))
with Path('web/mind-demo.js').open('a') as output:output.write('\nconst mindDemoDatabase='+json.dumps(database,separators=(',',':'))+';\n')
