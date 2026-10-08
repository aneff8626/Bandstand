import gzip
"""Rebuild derived masked contexts from saved raw EEG; preserve original recordings."""
import sys,json,io
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from private_storage import DATA_ROOT
from sequence_decoder import context_tokens

def reprocess(root=DATA_ROOT/'typing'):
 report=[]
 for directory in sorted(Path(root).iterdir()):
  if not directory.is_dir() or not (directory/'trials.jsonl').exists() or not ((directory/'continuous.csv').exists() or (directory/'continuous.csv.gz').exists()):continue
  session=json.loads((directory/'session.json').read_text());source=directory/'continuous.csv';lines=source.read_text().splitlines() if source.exists() else gzip.open(directory/'continuous.csv.gz','rt').read().splitlines()
  # The final row may be incomplete if this is a snapshot of an active recording.
  lines=[line for line in lines[1:] if len(line.split(','))==9]
  if not lines:continue
  data=np.loadtxt(io.StringIO('\n'.join(lines)),delimiter=',',ndmin=2);t=data[:,0];rows=[]
  for line in (directory/'trials.jsonl').read_text().splitlines():
   try:r=json.loads(line)
   except ValueError:continue
   if not r.get('label') or r.get('cancelled') or r.get('unsupported') or r.get('incomplete'):continue
   seq,q,pos,quality=context_tokens(t,data[:,1:5],data[:,5:9],r['onset'],session.get('history_seconds',30),session.get('prediction_delay',0))
   r['accepted']['context']=quality['usable'];r['reasons']['context']=[] if quality['usable'] else [quality['reason']];r['context_quality']=quality;r['context_file']=directory.name+'/'+r['id']+'.context.npz';r['context_block']=directory.name+':'+str(int((r['onset']-session['started'])//120));r['context_reprocessed']=True
   np.savez_compressed(Path(root)/r['context_file'],sequence=seq,quality=q,positions=pos);rows.append(r)
  temp=directory/'context_trials.jsonl.tmp';temp.write_text(''.join(json.dumps(r)+'\n' for r in rows));temp.replace(directory/'context_trials.jsonl')
  report.append(dict(session=directory.name,words=len(rows),usable=sum(r['accepted']['context'] for r in rows),excluded=sum(not r['accepted']['context'] for r in rows)))
 (Path(root)/'context_reprocessing_review.json').write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':print(json.dumps(reprocess(),indent=2))
