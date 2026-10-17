"""Milestone-four rehearsal: protected federation with synthetic participants (Flower SecAgg+, distributed
Gaussian noise, RDP privacy ledger). Synthetic data only; nothing touches the app, accounts or the network.

  .venv-fed/bin/python -m federation.run_synthetic          # all scenarios, report in build/federation/<run>/
Each scenario runs in its own process and leaves a spool: plaintext updates (harness-only evidence), every
reply the coordinator received, aggregates, published rounds and the privacy ledger."""
import glob,json,math,os,pickle,secrets,subprocess,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=dict(seed=11,clients=8,rounds=3,features=8,examples=60,lr=.5,clip=.5,sigma=0.0,announced_cohort=5,client_floor=5,threshold=5,clipping_range=8.0,epsilon_budget=1e9,delta=1e-6,no_noise_test_mode=True)
SCENARIOS={
 'F0_detector_control':{'rounds':1,'plain_control':True},
 'F1_rounds':{},
 'F2_dropout':{'rounds':1,'drop':{'1':[1,4]}},
 'F3_below_threshold':{'rounds':1,'threshold':6,'drop':{'1':[0,1,2]}},
 'F4_lying_coordinator':{'rounds':1,'wrong_parent':['1']},
 'F5_replay':{'rounds':2,'round_ids':{'1':'reused-id','2':'reused-id'}},
 'F6_cohort_below_floor':{'rounds':1,'announced_cohort':2},
 'F7_privacy_budget':{'rounds':4,'sigma':1.0,'epsilon_budget':None,'no_noise_test_mode':False},
 'F8_poisoning':{'rounds':1,'poison':[3],'poison_value':1e3},
}

def one(name,run):
 sys.path.insert(0,str(ROOT));os.environ['PYTHONPATH']=str(ROOT)
 from federation import secure_round as sr,privacy
 from flwr.simulation import run_simulation
 cfg={**BASE,**SCENARIOS[name],'run':run,'canary':'CANARY-'+secrets.token_hex(6)}
 if cfg['epsilon_budget'] is None:cfg['epsilon_budget']=(privacy.epsilon([1.0,1.0],cfg['delta'])+privacy.epsilon([1.0]*3,cfg['delta']))/2  # admits two releases, not three (illustrative only)
 out=ROOT/'build/federation'/run/name;cfg.update(work=str(out/'work'),spool=str(out/'spool'))
 (out/'work').mkdir(parents=True,exist_ok=True);(out/'spool').mkdir(exist_ok=True);(out/'config.json').write_text(json.dumps(cfg))
 try:run_simulation(server_app=sr.server_app(cfg),client_app=sr.client_app(cfg),num_supernodes=cfg['clients'],backend_config={'client_resources':{'num_cpus':1,'num_gpus':0.0}})
 except Exception as e:(out/'spool'/'run-error.txt').write_text(f'{type(e).__name__}: {e}'[:500])

# ---------- analysis (runs in the parent, with numpy only) ----------
def plain(spool,r):return {int(p.split('-p')[-1][:-4]):np.load(p) for p in glob.glob(f'{spool}/plain-r{r}-p*.npy')}
def published(spool):return sorted(int(Path(p).stem.split('-r')[1]) for p in glob.glob(f'{spool}/published-r*.json'))
def received_arrays(spool):
 from flwr.common import bytes_to_ndarray
 for p in sorted(glob.glob(f'{spool}/coordinator-received-*.pkl')):
  raw=Path(p).read_bytes();seen=pickle.loads(raw)
  for r in seen['configs'].values():
   for v in r.values():
    for item in (v if isinstance(v,list) else [v]):
     if isinstance(item,(bytes,bytearray)) and len(item)>200:
      try:yield raw,bytes_to_ndarray(item)
      except Exception:pass
  for arrays in seen['arrays'].values():
   for a in arrays:yield raw,a
def coordinator_view(spool,cfg):
 """Largest |correlation| between anything the coordinator received and any one participant's update."""
 deltas=[d.ravel() for r in range(1,cfg['rounds']+1) for d in plain(spool,r).values()];best=0.;compared=0;canary=False
 for raw,a in received_arrays(spool):
  canary=canary or cfg['canary'].encode() in raw
  a=np.asarray(a,float).ravel()
  for d in deltas:
   if a.size==d.size and a.std()>0 and d.std()>0:compared+=1;best=max(best,abs(float(np.corrcoef(a,d)[0,1])))
 for p in glob.glob(f'{spool}/coordinator-received-*.pkl'):canary=canary or cfg['canary'].encode() in Path(p).read_bytes()
 return best,compared,canary
def heldout_loss(cfg,weights):
 r=np.random.default_rng(cfg['seed']*1000+99);rr=np.random.default_rng(cfg['seed']);w=rr.normal(scale=.3,size=(cfg['features']+1,384))
 x=r.normal(size=(200,cfg['features']))+r.normal(scale=.3,size=cfg['features']);a=np.c_[x,np.ones(200)]
 y=a@w+r.normal(scale=.2,size=(200,384));y/=np.linalg.norm(y,axis=1,keepdims=True)
 return float(((a@weights-y)**2).sum(1).mean())

def check(name,out):
 cfg=json.loads((out/'config.json').read_text());spool=str(out/'spool');pub=published(spool);err=(out/'spool'/'run-error.txt')
 note=err.read_text() if err.exists() else ''
 def exact(r,survivors=None):
  p=plain(spool,r);ref=np.mean([p[k] for k in sorted(p) if survivors is None or k in survivors],0);agg=np.load(f'{spool}/aggregate-r{r}.npy')
  return float(np.abs(agg-ref).max()),float(np.abs(ref).max()),len(p)
 if name=='F0_detector_control':
  best,compared,_=coordinator_view(spool,cfg)
  return best>.99,f"without secure aggregation the coordinator receives each update: max |corr| {best:.3f} over {compared} comparisons, so the F1 detector can see a leak"
 if name=='F1_rounds':
  errs=[exact(r) for r in pub];best,compared,canary=coordinator_view(spool,cfg)
  losses=[heldout_loss(cfg,np.zeros((cfg['features']+1,384)))]+[heldout_loss(cfg,np.load(f'{spool}/model-r{r}.npy')) for r in pub]
  ok=pub==[1,2,3] and all(e<1e-4 for e,_,_ in errs) and compared>0 and best<.1 and not canary and losses[-1]<losses[0]
  return ok,f"published rounds {pub}; max |aggregate − plaintext mean| {max(e for e,_,_ in errs):.1e} (updates up to {max(s for _,s,_ in errs):.3f}); coordinator arrays compared {compared}, max |corr| with any one update {best:.3f}; canary text seen by coordinator: {canary}; held-out loss {losses[0]:.3f} → {losses[-1]:.3f}"
 if name=='F2_dropout':
  e,s,n=exact(1);info=json.loads((out/'spool'/'published-r1.json').read_text())
  return pub==[1] and n==6 and info['participants']==6 and e<1e-4,f"2 of 8 dropped after key sharing ({info['failures']} failed protocol messages); published with {info['participants']} participants; aggregate equals the survivors' mean (max error {e:.1e})"
 if name=='F3_below_threshold':
  return pub==[] and not glob.glob(f'{spool}/aggregate-r1.npy'),f"5 survivors below threshold 6: no aggregate, nothing published {('('+note[:120]+')') if note else ''}"
 if name=='F4_lying_coordinator':
  return pub==[] and not plain(spool,1),'every participant refused a manifest whose parent hash did not match the model it received; nothing published'
 if name=='F5_replay':
  return pub==[1] and not plain(spool,2),f'round 1 published; the reused round id in round 2 was refused by every participant (published {pub})'
 if name=='F6_cohort_below_floor':
  return pub==[] and not plain(spool,1),'announced cohort 2 is below the participants\' floor of 5: all refused; nothing published'
 if name=='F7_privacy_budget':
  ledger=json.loads((out/'spool'/'ledger.json').read_text());refused=sorted(int(Path(p).name.split('-r')[1]) for p in glob.glob(f'{spool}/refused-r*'))
  p=plain(spool,1);agg=np.load(f'{spool}/aggregate-r1.npy');resid=(agg-np.mean(list(p.values()),0)).std()
  expected=cfg['sigma']*cfg['clip']*math.sqrt(len(p)/cfg['announced_cohort'])/len(p)
  sys.path.insert(0,str(ROOT));from federation import privacy
  eps=[privacy.epsilon([1.0]*k,cfg['delta']) for k in (1,2,3)]
  ok=pub==[1,2] and refused==[3,4] and abs(resid/expected-1)<.15
  return ok,f"budget ε={cfg['epsilon_budget']:.2f} (δ={cfg['delta']}, illustrative): published {pub}, refused {refused}; ε after 1/2/3 releases at σ=1: {eps[0]:.2f}/{eps[1]:.2f}/{eps[2]:.2f}; noise in the mean {resid:.4f} vs expected {expected:.4f}"
 if name=='F8_poisoning':
  p=plain(spool,1);honest=np.mean([v for k,v in p.items() if k!=3],0);agg=np.load(f'{spool}/aggregate-r1.npy');shift=float(np.abs(agg-honest).max());l2=float(np.linalg.norm(agg-honest))
  return 'observed',f"one participant sent {cfg['poison_value']:g} per coordinate; SecAgg+ clipped it to ±{cfg['clipping_range']} per coordinate, still moving the mean by up to {shift:.2f} per coordinate (L2 {l2:.1f}) against an honest update norm ≤ {cfg['clip']}. Masking hides individual updates, so the coordinator cannot inspect or reject this; bounded robustness needs a reviewed design (e.g. lower per-coordinate range plus norm proofs or robust aggregation)."
 return False,'unknown scenario'

def main():
 if len(sys.argv)==4 and sys.argv[1]=='--one':return one(sys.argv[2],sys.argv[3])
 run=time.strftime('%Y%m%d-%H%M%S');results=[]
 for name in SCENARIOS:
  start=time.time()
  proc=subprocess.run([sys.executable,'-m','federation.run_synthetic','--one',name,run],cwd=ROOT,capture_output=True,text=True,timeout=900,env={**os.environ,'PYTHONPATH':str(ROOT)})
  out=ROOT/'build/federation'/run/name;(out/'log.txt').write_text(proc.stdout[-20000:]+proc.stderr[-20000:])
  try:ok,evidence=check(name,out)
  except Exception as e:ok,evidence=False,f'{type(e).__name__}: {e}'
  outcome='observed' if ok=='observed' else 'pass' if ok else 'fail'
  results.append({'id':name.split('_')[0],'scenario':name,'outcome':outcome,'seconds':round(time.time()-start),'evidence':evidence})
  print(f"{outcome:>8}  {name}  ({results[-1]['seconds']} s)  {evidence}",flush=True)
 rows=['| ID | Scenario | Outcome | Evidence |','|---|---|---|---|']+[f"| {r['id']} | {r['scenario']} | {r['outcome']} | {r['evidence']} |" for r in results]
 report=ROOT/'build/federation'/run/'report.md';report.write_text(f'# Synthetic federation run {run}\n\nFlower SecAgg+ with {BASE["clients"]} synthetic participants. Synthetic data only.\n\n'+'\n'.join(rows)+'\n')
 (ROOT/'build/federation'/run/'report.json').write_text(json.dumps(results,indent=2))
 print(json.dumps({o:sum(r['outcome']==o for r in results) for o in ('pass','fail','observed')}),'->',report)
 sys.exit(1 if any(r['outcome']=='fail' for r in results) else 0)

if __name__=='__main__':main()
