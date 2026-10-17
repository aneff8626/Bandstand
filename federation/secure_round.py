"""Synthetic secure-aggregation rounds for the shared writing decoder, on Flower's SecAgg+ (Bell et al. 2020,
building on Bonawitz et al. 2017). TEST HARNESS ONLY: synthetic participants and synthetic text; nothing here
is used by the app, and no participant data exists in it.

Client side, per round, each simulated participant:
- checks the round against the model it received (parent hash), its own record of rounds (no replays), the
  announced minimum cohort (refuses below a floor it holds itself) and the pinned encoder,
- computes one clipped update with shared_learning.local_round_update on its own synthetic archive and passes
  it through shared_learning.contribution's checks,
- adds its share of Gaussian noise (sigma*C/sqrt(min_cohort)), so the SUM carries noise of at least sigma*C
  whenever min_cohort honest participants contribute (distributed noise; the server never holds an unnoised
  aggregate),
- returns the noised update with weight 1 (participants weighted equally) through secaggplus_mod, which masks
  it before it leaves.
Server side, the coordinator only ever handles masked vectors and key shares; it learns the average. It
publishes a round only if the privacy ledger allows it. A recording wrapper keeps every reply the coordinator
receives so the harness can show that none of them is an individual update."""
import hashlib,json,math,os,pickle
from pathlib import Path
import numpy as np
from flwr.client import ClientApp,NumPyClient
from flwr.client.mod import secaggplus_mod
from flwr.common import Context,MessageType,ndarrays_to_parameters,parameters_to_ndarrays
from flwr.common.secure_aggregation.secaggplus_constants import Key,Stage
from flwr.server import LegacyContext,ServerApp,ServerConfig
from flwr.server.strategy import FedAvg
from flwr.server.workflow import DefaultWorkflow,SecAggPlusWorkflow
import shared_learning,shared_model
from cumulative_semantic import connect,blob,SCHEMA
from federation.privacy import Ledger
RECORD_KEY_CONFIGS=secaggplus_mod.__globals__['RECORD_KEY_CONFIGS']

def model_hash(arrays):return hashlib.sha256(b''.join(np.asarray(a,'<f4').tobytes() for a in arrays)).hexdigest()

def truth(cfg):
 r=np.random.default_rng(cfg['seed']);return r.normal(scale=.3,size=(cfg['features']+1,shared_model.EMBEDDING))

def synthetic_archive(cfg,pid,root):
 """One participant's private archive: EEG-like features with a participant-specific shift, targets from a
 shared hidden mapping plus noise, and canary texts that must never leave."""
 db=connect(root)
 if db.execute('SELECT count(*) FROM examples').fetchone()[0]:return db
 r=np.random.default_rng(cfg['seed']*1000+pid);w=truth(cfg);shift=r.normal(scale=.3,size=cfg['features'])
 for i in range(cfg['examples']):
  x=r.normal(size=cfg['features'])+shift;y=np.r_[x,1.]@w+r.normal(scale=.2,size=shared_model.EMBEDDING);y/=np.linalg.norm(y)
  db.execute('INSERT INTO examples VALUES (?,?,?,?,?,?,?,?,?,?)',(f'{pid}-{i:05d}','s',float(i),float(i)+1,f"{cfg['canary']} participant {pid} phrase {i}",cfg['canary'],blob(x),blob(np.ones(cfg['features'])),blob(y),blob(np.zeros(shared_model.EMBEDDING))))
 db.commit();return db

class Participant(NumPyClient):
 def __init__(self,cfg,pid):self.cfg=cfg;self.pid=pid;self.home=Path(cfg['work'])/f'participant-{pid}';self.home.mkdir(parents=True,exist_ok=True)
 def fit(self,parameters,config):
  cfg=self.cfg;mean,scale,weights=parameters
  manifest={'feature_schema':config['feature_schema'],'model_family':config['model_family'],'encoder':json.loads(config['encoder']),'round_id':config['round_id'],
   'parent_model_sha256':config['parent_model_sha256'],'learning_rate':float(config['learning_rate']),'clip_norm':float(config['clip_norm'])}
  if model_hash(parameters)!=manifest['parent_model_sha256']:raise ValueError('Round manifest does not match the model received')
  if int(config['min_cohort'])<cfg['client_floor']:raise ValueError('Announced cohort is below this participant\'s floor')
  seen=self.home/'rounds.json';rounds=json.loads(seen.read_text()) if seen.exists() else []
  if manifest['round_id'] in rounds:raise ValueError('Round already answered (replay)')
  seen.write_text(json.dumps(rounds+[manifest['round_id']]))
  db=synthetic_archive(cfg,self.pid,self.home)
  try:update=shared_learning.local_round_update(db,manifest,mean,scale,weights,consent=True)
  finally:db.close()
  shared_learning.contribution(update,manifest['clip_norm'])  # shape, finiteness and norm checks
  delta=update['delta'].astype(float)
  if self.pid in cfg.get('poison',[]):delta=np.full_like(delta,cfg['poison_value'])  # a malicious client ignoring the protocol
  noise=np.random.default_rng([cfg['seed'],self.pid,int(config['round_number'])]).normal(scale=float(config['noise_multiplier'])*manifest['clip_norm']/math.sqrt(int(config['min_cohort'])),size=delta.shape)
  # Harness-only spool of the plaintext update, used to check the aggregate and the coordinator's view.
  np.save(Path(cfg['spool'])/f"plain-r{config['round_number']}-p{self.pid}.npy",delta)
  return [(delta+noise).astype(np.float32)],1,{}

def client_app(cfg):
 def drop_mod(msg,ctxt,call_next):
  if msg.metadata.message_type==MessageType.TRAIN:
   configs=msg.content.config_records.get(RECORD_KEY_CONFIGS)
   pid=int(ctxt.node_config['partition-id'])
   if configs is not None and configs.get(Key.STAGE)==Stage.COLLECT_MASKED_VECTORS and pid in cfg.get('drop',{}).get(str(msg.metadata.group_id),[]):
    raise RuntimeError('simulated dropout after key sharing')
  return call_next(msg,ctxt)
 def client_fn(context:Context):return Participant(cfg,int(context.node_config['partition-id'])).to_client()
 # plain_control: detector control only; updates travel unmasked, as in ordinary federated averaging.
 return ClientApp(client_fn=client_fn,mods=[drop_mod] if cfg.get('plain_control') else [drop_mod,secaggplus_mod])

class SharedDecoderStrategy(FedAvg):
 def __init__(self,cfg,initial):
  n=cfg['clients'];super().__init__(fraction_fit=1.0,fraction_evaluate=0.0,min_fit_clients=n,min_available_clients=n,initial_parameters=ndarrays_to_parameters(initial))
  self.cfg=cfg;self.model=[np.asarray(a,np.float32) for a in initial]
  self.ledger=Ledger(Path(cfg['spool'])/'ledger.json',cfg['epsilon_budget'],cfg['delta'])
 def configure_fit(self,server_round,parameters,client_manager):
  cfg=self.cfg;arrays=parameters_to_ndarrays(parameters)
  config={'round_number':server_round,'round_id':cfg.get('round_ids',{}).get(str(server_round),f"{cfg['run']}-r{server_round}"),'parent_model_sha256':model_hash(arrays),
   'feature_schema':SCHEMA,'model_family':shared_model.FAMILY,'encoder':json.dumps(shared_model.ENCODER),'learning_rate':cfg['lr'],'clip_norm':cfg['clip'],
   'noise_multiplier':cfg['sigma'],'min_cohort':cfg['announced_cohort']}
  if str(server_round) in cfg.get('wrong_parent',[]):config['parent_model_sha256']='0'*64  # a coordinator lying about the model
  return [(client,type(fitins)(fitins.parameters,config)) for client,fitins in super().configure_fit(server_round,parameters,client_manager)]
 def aggregate_fit(self,server_round,results,failures):
  if not results:return None,{}
  mean_delta=parameters_to_ndarrays(results[0][1].parameters)[0]
  np.save(Path(self.cfg['spool'])/f'aggregate-r{server_round}.npy',mean_delta)
  if self.cfg['sigma']==0 and self.cfg.get('no_noise_test_mode'):spent=float('inf')  # exactness tests only; never a release
  elif not self.ledger.allows(self.cfg['sigma']):
   (Path(self.cfg['spool'])/f'refused-r{server_round}').write_text('privacy budget');return None,{}
  else:spent=self.ledger.record(f'r{server_round}',self.cfg['sigma'])
  self.model=[self.model[0],self.model[1],(self.model[2]+mean_delta).astype(np.float32)]
  np.save(Path(self.cfg['spool'])/f'model-r{server_round}.npy',self.model[2])
  (Path(self.cfg['spool'])/f'published-r{server_round}.json').write_text(json.dumps({'participants':len(results),'failures':len(failures),'epsilon_spent':spent}))
  return ndarrays_to_parameters(self.model),{}

class RecordingGrid:
 """Pass-through grid that keeps every reply the coordinator receives (harness evidence only)."""
 def __init__(self,grid,spool):self._grid=grid;self._spool=Path(spool);self._n=0
 def __getattr__(self,name):return getattr(self._grid,name)
 def send_and_receive(self,messages,*,timeout=None):
  replies=list(self._grid.send_and_receive(messages,timeout=timeout))
  for m in replies:
   if not m.has_content():continue
   seen={'arrays':{k:[a.numpy() for a in r.values()] for k,r in m.content.array_records.items()},
         'configs':{k:{kk:vv for kk,vv in r.items()} for k,r in m.content.config_records.items()}}
   (self._spool/f'coordinator-received-{self._n:05d}.pkl').write_bytes(pickle.dumps(seen));self._n+=1
  return replies

def server_app(cfg):
 app=ServerApp()
 @app.main()
 def main(grid,context):
  initial=[np.zeros(cfg['features'],np.float32),np.ones(cfg['features'],np.float32),np.zeros((cfg['features']+1,shared_model.EMBEDDING),np.float32)]
  strategy=SharedDecoderStrategy(cfg,initial)
  legacy=LegacyContext(context=context,config=ServerConfig(num_rounds=cfg['rounds']),strategy=strategy)
  # max_weight=1: every participant has weight 1, so no one can count more, and quantization keeps full precision.
  fit=SecAggPlusWorkflow(num_shares=cfg['clients'],reconstruction_threshold=cfg['threshold'],max_weight=1.0,clipping_range=cfg['clipping_range'],timeout=cfg.get('timeout',60))
  (DefaultWorkflow() if cfg.get('plain_control') else DefaultWorkflow(fit_workflow=fit))(RecordingGrid(grid,cfg['spool']),legacy)
 return app
