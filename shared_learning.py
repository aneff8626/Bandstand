"""Local-only adapter for future federated rounds. No transport or upload API.

Individual updates can leak private training data. Do not serialize/send these
without a separately reviewed secure-aggregation and privacy implementation.
"""
import numpy as np
from cumulative_semantic import SCHEMA,batches

def local_round_update(db,manifest,mean,scale,weights,*,consent=False):
 """One bounded gradient step in a common coordinate system, then norm clip.

Only an in-memory numeric delta and count are returned. This is NOT secure
aggregation or differential privacy. The app does not call this function yet.
"""
 if not consent:raise PermissionError('Explicit shared-learning consent required')
 if manifest.get('feature_schema')!=SCHEMA or manifest.get('model_family')!='semantic-ridge-gradient-v1':raise ValueError('Incompatible shared model')
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
  grad+=a.T@(a@weights-y);count+=len(x)
 if count<8:raise ValueError('At least eight local examples required')
 delta=-rate*grad/count;norm=np.linalg.norm(delta)
 if not np.isfinite(norm):raise ValueError('Invalid update')
 delta*=min(1.,clip/max(norm,1e-12))
 return {'delta':delta.astype('f'),'examples':count,'round_id':manifest['round_id'],'parent_model_sha256':manifest['parent_model_sha256'],'transport_enabled':False}
