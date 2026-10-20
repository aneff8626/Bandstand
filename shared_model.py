"""Signed shared-model releases for the writing decoder: numeric tensors only, verified before loading.

A release is one file: b'BSM1', a 4-byte little-endian header length, a UTF-8 JSON header, then the tensors
as little-endian float32 in header order. Nothing is unpickled or executed. A release loads only if its
Ed25519 signature matches a trusted key built into the app, its header and tensors match the allowlisted
layout, the feature schema, model family and pinned public encoder match this installation, and every
value is finite. The last good release is kept for rollback.

No release key is trusted yet (TRUSTED_KEYS is empty), so the app loads no shared model. The private key
stays offline with the project; only its public half belongs here."""
import hashlib,json,os,struct
from pathlib import Path
import numpy as np
from cumulative_semantic import SCHEMA
MAGIC=b'BSM1';FORMAT='bandstand-shared-model-v1';FAMILY='semantic-ridge-gradient-v1'
ENCODER={'repo':'sentence-transformers/all-MiniLM-L6-v2','revision':'1110a243fdf4706b3f48f1d95db1a4f5529b4d41'}
EMBEDDING=384;MAX_FEATURES=4096;MAX_BYTES=64*1024*1024
TRUSTED_KEYS=()  # raw 32-byte Ed25519 public keys, hex; empty: no shared model is trusted
HEADER_KEYS={'format','version','model_family','feature_schema','encoder','features','tensors','parent_model_sha256','evaluation','privacy'}
TENSORS=('mean','scale','weights')

def shapes(features):return {'mean':(features,),'scale':(features,),'weights':(features+1,EMBEDDING)}

def pack(version,mean,scale,weights,parent='',evaluation=None,privacy=None):
 """Build an unsigned release body. Only numbers and fixed identifiers go in the header."""
 arrays={'mean':np.asarray(mean,'<f4'),'scale':np.asarray(scale,'<f4'),'weights':np.asarray(weights,'<f4')}
 features=arrays['mean'].shape[0] if arrays['mean'].ndim==1 else -1
 _check_arrays(arrays,features)
 header={'format':FORMAT,'version':str(version),'model_family':FAMILY,'feature_schema':SCHEMA,'encoder':ENCODER,'features':features,
  'tensors':[{'name':n,'shape':list(arrays[n].shape),'sha256':hashlib.sha256(arrays[n].tobytes()).hexdigest()} for n in TENSORS],
  'parent_model_sha256':parent,'evaluation':_numbers(evaluation or {}),'privacy':_numbers(privacy or {})}
 raw=json.dumps(header,sort_keys=True,separators=(',',':')).encode()
 return MAGIC+struct.pack('<I',len(raw))+raw+b''.join(arrays[n].tobytes() for n in TENSORS)

def sign(body,private_key):
 """Return body + 64-byte Ed25519 signature. Used by the offline release tool, never by the app."""
 return body+private_key.sign(body)

def _numbers(d):
 if not isinstance(d,dict) or len(d)>32:raise ValueError('Release metadata must be a small object of numbers')
 for k,v in d.items():
  if not isinstance(k,str) or len(k)>40 or not k.replace('_','').isalnum() or type(v) not in (int,float) or not np.isfinite(v):raise ValueError('Release metadata must be numbers')
 return d

def _check_arrays(arrays,features):
 if not 1<=features<=MAX_FEATURES:raise ValueError('Invalid feature dimension')
 for name,shape in shapes(features).items():
  a=arrays[name]
  if a.shape!=shape or a.dtype!=np.dtype('<f4'):raise ValueError(f'Invalid {name} tensor')
  if not np.isfinite(a).all():raise ValueError(f'Non-finite {name} tensor')
 if np.any(arrays['scale']<=0):raise ValueError('Scale must be positive')

def verify(data,trusted=None):
 """Return (header, tensors) for a valid signed release, else raise ValueError. Never executes content."""
 trusted=TRUSTED_KEYS if trusted is None else trusted
 if not trusted:raise ValueError('No shared-model release key is trusted on this installation.')
 if not isinstance(data,(bytes,bytearray)) or not 72<len(data)<=MAX_BYTES:raise ValueError('Invalid release size')
 body,signature=bytes(data[:-64]),bytes(data[-64:])
 from cryptography.exceptions import InvalidSignature
 from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
 for key in trusted:
  try:Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(signature,body);break
  except (InvalidSignature,ValueError):continue
 else:raise ValueError('Release signature is not from a trusted key.')
 if body[:4]!=MAGIC:raise ValueError('Not a shared-model release')
 (n,)=struct.unpack('<I',body[4:8])
 if n>65536 or 8+n>len(body):raise ValueError('Invalid release header')
 try:header=json.loads(body[8:8+n].decode())
 except (UnicodeError,ValueError):raise ValueError('Invalid release header') from None
 if not isinstance(header,dict) or set(header)!=HEADER_KEYS:raise ValueError('Unexpected release header fields')
 if header['format']!=FORMAT or header['model_family']!=FAMILY:raise ValueError('Unsupported release format')
 if header['feature_schema']!=SCHEMA:raise ValueError('Release was trained on a different feature schema')
 if header['encoder']!=ENCODER:raise ValueError('Release expects a different public text encoder')
 features=header['features']
 if type(features) is not int:raise ValueError('Invalid feature dimension')
 _numbers(header['evaluation']);_numbers(header['privacy'])
 spec=shapes(features) if 1<=features<=MAX_FEATURES else {}
 listed=header['tensors']
 if not isinstance(listed,list) or [t.get('name') if isinstance(t,dict) else None for t in listed]!=list(TENSORS):raise ValueError('Unexpected tensors')
 offset=8+n;arrays={}
 for t in listed:
  if set(t)!={'name','shape','sha256'} or tuple(t['shape'])!=spec.get(t['name']):raise ValueError('Unexpected tensor shape')
  size=int(np.prod(t['shape']))*4;chunk=body[offset:offset+size];offset+=size
  if len(chunk)!=size or hashlib.sha256(chunk).hexdigest()!=t['sha256']:raise ValueError('Tensor hash mismatch')
  arrays[t['name']]=np.frombuffer(chunk,'<f4').reshape(t['shape']).copy()
 if offset!=len(body):raise ValueError('Unexpected trailing data')
 _check_arrays(arrays,features)
 return header,arrays

def install(root,data,trusted=None):
 """Verify and store a release; the previous good release is kept for rollback."""
 header,_=verify(data,trusted)
 folder=Path(root)/'shared-models';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
 digest=hashlib.sha256(data).hexdigest();target=folder/f'{digest}.bsm'
 temp=target.with_suffix('.tmp');temp.write_bytes(data);temp.chmod(0o600);os.replace(temp,target)
 state=_state(folder);previous=state.get('current')
 if previous!=digest:state={'current':digest,'previous':previous}
 _save_state(folder,state);return header,digest

def current(root,trusted=None):
 """Load the active release, re-verifying it; falls back to the previous good one if it no longer verifies."""
 folder=Path(root)/'shared-models';state=_state(folder)
 for key in ('current','previous'):
  digest=state.get(key)
  if not digest:continue
  try:return verify((folder/f'{digest}.bsm').read_bytes(),trusted)
  except (OSError,ValueError):continue
 return None

def rollback(root):
 folder=Path(root)/'shared-models';state=_state(folder)
 if not state.get('previous'):raise ValueError('No earlier shared model to return to')
 _save_state(folder,{'current':state['previous'],'previous':None})

def _state(folder):
 try:return json.loads((folder/'state.json').read_text())
 except (OSError,ValueError):return {}
def _save_state(folder,state):
 temp=folder/'state.tmp';temp.write_text(json.dumps(state));temp.chmod(0o600);os.replace(temp,folder/'state.json')
