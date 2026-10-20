"""Local-only adapter for future federated rounds. No transport or upload API.

Individual updates can leak private training data. Do not serialize/send these
without a separately reviewed secure-aggregation and privacy implementation.
"""
import hashlib,json,re,struct
import numpy as np
from cumulative_semantic import SCHEMA,batches
from semantic_decoder import memory_check
import shared_model

def local_round_update(db,manifest,mean,scale,weights,*,consent=False):
 """One bounded gradient step in a common coordinate system, then norm clip.

Only an in-memory numeric delta and count are returned. This is NOT secure
aggregation or differential privacy. The app does not call this function yet.
"""
 if not consent:raise PermissionError('Explicit shared-learning consent required')
 if manifest.get('feature_schema')!=SCHEMA or manifest.get('model_family')!='semantic-ridge-gradient-v1':raise ValueError('Incompatible shared model')
 # Targets come from the local public encoder; a different encoder revision would train a different objective.
 if manifest.get('encoder')!=shared_model.ENCODER:raise ValueError('Shared round expects a different public text encoder')
 if not manifest.get('round_id') or not manifest.get('parent_model_sha256'):raise ValueError('Round and parent model identity required')
 rate=float(manifest.get('learning_rate',.01));clip=float(manifest.get('clip_norm',1.))
 if not 0<rate<=1 or not 0<clip<=10:raise ValueError('Invalid round bounds')
 mean=np.asarray(mean,float);scale=np.asarray(scale,float);weights=np.asarray(weights,float)
 if mean.ndim!=1 or scale.shape!=mean.shape or weights.ndim!=2 or weights.shape[0]!=len(mean)+1:raise ValueError('Invalid model shapes')
 if not all(np.isfinite(a).all() for a in (mean,scale,weights)) or np.any(scale<=0):raise ValueError('Invalid model values')
 grad=np.zeros_like(weights);count=0
 for x,y in batches(db):
  if x.shape[1]!=len(mean) or y.shape[1]!=weights.shape[1]:raise ValueError('Feature or embedding dimension mismatch')
  a=np.c_[np.clip((x-mean)/scale,-8,8),np.ones(len(x))]
  grad+=a.T@(a@weights-y);count+=len(x);memory_check()
 if count<8:raise ValueError('At least eight local examples required')
 delta=-rate*grad/count;norm=np.linalg.norm(delta)
 if not np.isfinite(norm):raise ValueError('Invalid update')
 delta*=min(1.,clip/max(norm,1e-12))
 return {'delta':delta.astype('f'),'examples':count,'round_id':manifest['round_id'],'parent_model_sha256':manifest['parent_model_sha256'],'transport_enabled':False}

# Contribution wire format: b'BSC1', 4-byte header length, JSON header, little-endian float32 delta.
# The header carries only the round, the parent model hash, the shape and a hash. The example count is
# deliberately left out: participants are weighted equally, and a count would reveal how much someone wrote.
CMAGIC=b'BSC1';CFORMAT='bandstand-contribution-v1'
ROUND=re.compile(r'[A-Za-z0-9_-]{1,64}');HEX64=re.compile(r'[0-9a-f]{64}')

def contribution(update,clip_norm):
 """Serialize one clipped update for a secure-aggregation client. Numbers and identifiers only."""
 delta=np.asarray(update['delta'],'<f4');_check_delta(delta,clip_norm)
 if not ROUND.fullmatch(str(update['round_id'])) or not HEX64.fullmatch(str(update['parent_model_sha256'])):raise ValueError('Invalid round identity')
 header={'format':CFORMAT,'round_id':update['round_id'],'parent_model_sha256':update['parent_model_sha256'],'shape':list(delta.shape),'sha256':hashlib.sha256(delta.tobytes()).hexdigest()}
 raw=json.dumps(header,sort_keys=True,separators=(',',':')).encode()
 return CMAGIC+struct.pack('<I',len(raw))+raw+delta.tobytes()

def read_contribution(data,manifest,features):
 """Coordinator-side check of one contribution against the round it claims. Raises ValueError."""
 if not isinstance(data,(bytes,bytearray)) or len(data)<8 or data[:4]!=CMAGIC:raise ValueError('Not a contribution')
 (n,)=struct.unpack('<I',data[4:8])
 if n>4096 or 8+n>len(data):raise ValueError('Invalid contribution header')
 try:header=json.loads(bytes(data[8:8+n]).decode())
 except (UnicodeError,ValueError):raise ValueError('Invalid contribution header') from None
 if not isinstance(header,dict) or set(header)!={'format','round_id','parent_model_sha256','shape','sha256'} or header['format']!=CFORMAT:raise ValueError('Unexpected contribution fields')
 if header['round_id']!=manifest['round_id'] or header['parent_model_sha256']!=manifest['parent_model_sha256']:raise ValueError('Contribution is for another round or model')
 shape=(features+1,shared_model.EMBEDDING)
 if tuple(header['shape'])!=shape or len(data)-8-n!=shape[0]*shape[1]*4:raise ValueError('Unexpected contribution shape')
 body=bytes(data[8+n:])
 if hashlib.sha256(body).hexdigest()!=header['sha256']:raise ValueError('Contribution hash mismatch')
 delta=np.frombuffer(body,'<f4').reshape(shape).copy();_check_delta(delta,float(manifest.get('clip_norm',1.)));return delta

def _check_delta(delta,clip_norm):
 if delta.ndim!=2 or delta.shape[1]!=shared_model.EMBEDDING or not 2<=delta.shape[0]<=shared_model.MAX_FEATURES+1:raise ValueError('Unexpected update shape')
 if not np.isfinite(delta).all():raise ValueError('Non-finite update')
 if float(np.linalg.norm(delta.astype(float)))>clip_norm*(1+1e-4):raise ValueError('Update exceeds the round clipping norm')

def _child(root,manifest,mean,scale,weights,out):
 import os
 from cumulative_semantic import connect
 try:os.nice(10)  # best effort; restricted environments may refuse priority changes
 except OSError:pass
 db=None
 try:
  db=connect(root)
  out.put(('ok',contribution(local_round_update(db,manifest,mean,scale,weights,consent=True),float(manifest.get('clip_norm',1.)))))
 except Exception as e:out.put(('error',type(e).__name__))  # no private paths/text in worker errors
 finally:
  if db is not None:db.close()

def train_isolated(root,manifest,model,*,consent=False,timeout=600):
 """Compute one contribution in a separate low-priority process with a time limit, so a slow or failing
 round never stalls EEG acquisition or saving. Returns the serialized contribution; uploads nothing."""
 if not consent:raise PermissionError('Explicit shared-learning consent required')
 import multiprocessing as mp
 ctx=mp.get_context('spawn');out=ctx.Queue()
 p=ctx.Process(target=_child,args=(str(root),manifest,*model,out),daemon=True);p.start()
 try:status,value=out.get(timeout=timeout)
 except Exception:
  p.kill();p.join(5);raise TimeoutError('Shared-learning round exceeded its time budget') from None
 p.join(5)
 if status!='ok':raise ValueError('Local shared-learning round failed: '+value)
 return value
