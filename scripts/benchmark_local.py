"""Synthetic acquisition/ERP/export benchmark. Never uses participant files/network."""
import sys,tempfile,time,json,resource,os
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
private_tmp=tempfile.TemporaryDirectory(prefix='bandstand-benchmark-private-')
os.environ['BANDSTAND_DATA_DIR']=private_tmp.name
from engine import Engine
from analysis import FS
rng=np.random.default_rng(9);start=time.perf_counter();durations=[]
with tempfile.TemporaryDirectory(prefix='bandstand-benchmark-') as tmp,patch('engine.ROOT',Path(tmp)),patch('engine.DATA_ROOT',Path(tmp)/'data'):
 e=Engine();origin=time.time();e.ingest(origin-4+np.arange(4*FS)/FS,rng.normal(0,2,(4*FS,4)))
 e.begin({'protocol':'oddball','trials':100,'channels':['TP9','TP10'],'allow_noisy_start':True})
 e.session['source']='simulation'
 for i in range(100):
  onset=origin+i*1.5
  with patch('engine.time.time',return_value=onset):e.event({'kind':'stimulus','index':i,'condition_index':int(i%4==0),'onset':onset})
  t=onset+np.arange(384)/FS;x=rng.normal(0,2,(384,4))
  if i%4==0:x[:,[0,3]]+=8*np.exp(-((t-onset-.35)/.07)**2)[:,None]
  began=time.perf_counter();e.ingest(t,x);e.process_pending();e.analysis();durations.append(time.perf_counter()-began)
 e.stop();assert len(e.trials)==100
 for kind in ('raw','processed','pdf'):
  data,mime,name=e.export(kind);assert len(data)>100
 bytes_saved=sum(p.stat().st_size for p in Path(tmp).rglob('*') if p.is_file())
 result={'synthetic_seconds':150,'trials':100,'wall_seconds':round(time.perf_counter()-start,3),'block_processing_p95_ms':round(float(np.percentile(durations,95))*1000,2),'peak_process_memory_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,1),'recording_bytes':bytes_saved,'exports_verified':['raw','processed','pdf'],'scope':'Offline synthetic ERP pipeline, not hardware timing or hours-long recording.'}
 print(json.dumps(result,indent=2))
