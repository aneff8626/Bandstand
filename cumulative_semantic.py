"""Disk-backed, cumulative local semantic training. Never a network client.

SQLite contains sensitive text/embeddings and stays beside private recordings.
Training uses every eligible archived example; bounded RAM and retrieval bank.
"""
import hashlib,json,os,sqlite3,time,uuid
from pathlib import Path
import numpy as np
from semantic_decoder import eeg_summary,encode,apply,unit,save_model,four_choice_scores,memory_check

SCHEMA='muse-context-multiscale-v1-minilm-l6-v2'
BATCH=64

def connect(root):
 db=sqlite3.connect(Path(root)/'semantic_archive.sqlite3')
 os.chmod(Path(root)/'semantic_archive.sqlite3',0o600)
 db.executescript('''
 CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
 CREATE TABLE IF NOT EXISTS sources(session TEXT PRIMARY KEY,signature TEXT);
 CREATE TABLE IF NOT EXISTS words(session TEXT,id TEXT,onset REAL,body TEXT,PRIMARY KEY(session,id));
 CREATE TABLE IF NOT EXISTS embeddings(key TEXT PRIMARY KEY,vector BLOB);
 CREATE TABLE IF NOT EXISTS examples(id TEXT PRIMARY KEY,session TEXT,onset REAL,end REAL,text TEXT,previous TEXT,x BLOB,q BLOB,y BLOB,h BLOB);
 CREATE INDEX IF NOT EXISTS examples_time ON examples(onset);
 ''')
 schema=db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
 if schema and schema[0]!=SCHEMA:raise ValueError('Archive feature schema changed; migrate before training')
 db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('schema',SCHEMA))
 db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('local_profile',str(uuid.uuid4())))
 db.commit();return db

def phrases(rows):
 import re
 group=[];prior='';previous=None
 def finish():
  if len(group)<3 or not group[0].get('accepted',{}).get('context') or not group[0].get('context_file'):return None
  return dict(text=' '.join(r.get('typed') or r['label'] for r in group)[:500],previous=prior,context_file=group[0]['context_file'],onset=group[0]['onset'],end=group[-1].get('committed',group[-1]['onset']),session=group[0]['session'])
 for r in rows:
  boundary=previous is not None and (r['session']!=previous['session'] or r.get('focus_id')!=previous.get('focus_id') or r['onset']-previous.get('committed',previous['onset'])>5)
  if boundary:
   p=finish()
   if p:yield p
   group=[];prior=''
  if not r.get('label') or any(r.get(k) for k in ('cancelled','unsupported','incomplete')):
   p=finish()
   if p:yield p
   group=[];prior=''
  else:
   group.append(r)
   if len(group)>=12 or re.search(r'[.!?;:]\W*$',r.get('typed','')):
    p=finish()
    if p:yield p;prior=p['text']
    group=[]
  previous=r
 # An unfinished tail is reconsidered when the source file grows.

def blob(a):return np.asarray(a,dtype='<f4').tobytes()
def array(b):return np.frombuffer(b,dtype='<f4')

def vectors(db,texts,encoder):
 keys=[hashlib.sha256((SCHEMA+'\0'+t).encode()).hexdigest() for t in texts]
 found={k:row[0] for k in set(keys) if (row:=db.execute('SELECT vector FROM embeddings WHERE key=?',(k,)).fetchone())}
 missing=list(dict.fromkeys(k for k in keys if k not in found))
 if missing:
  text_by_key=dict(zip(keys,texts));values=encoder([text_by_key[k] for k in missing])
  for k,v in zip(missing,values):
   if not np.isfinite(v).all():raise ValueError('Nonfinite semantic embedding')
   found[k]=blob(v);db.execute('INSERT OR REPLACE INTO embeddings VALUES (?,?)',(k,found[k]))
 return [found[k] for k in keys]

def index_archive(root,db,encoder=encode):
 root=Path(root);skipped=0
 present={p.parent.name for p in root.glob('*/trials.jsonl')}
 for (session,) in db.execute('SELECT session FROM sources').fetchall():
  if session not in present:
   for table in ('sources','words','examples'):db.execute(f'DELETE FROM {table} WHERE session=?',(session,))
 db.commit()
 for path in sorted(root.glob('*/trials.jsonl')):
  session=path.parent.name;files=[path,path.parent/'context_trials.jsonl']
  signature=json.dumps([(f.name,f.stat().st_size,f.stat().st_mtime_ns) for f in files if f.exists()])
  if db.execute('SELECT 1 FROM sources WHERE session=? AND signature=?',(session,signature)).fetchone():continue
  # Disk staging avoids loading an arbitrarily long recording into RAM.
  db.execute('DELETE FROM words WHERE session=?',(session,))
  for f in files:
   if not f.exists():continue
   with f.open() as stream:
    for line in stream:
     try:
      r=json.loads(line);ident=str(r['id']);onset=float(r['onset']);r['session']=session
      db.execute('INSERT OR REPLACE INTO words VALUES (?,?,?,?)',(session,ident,onset,json.dumps(r)))
     except (ValueError,KeyError,TypeError):skipped+=1
  # Rebuild changed sessions; publish no model until indexing completes.
  # Commit embedding batches so a timed-out backfill reuses the expensive work.
  db.execute('DELETE FROM examples WHERE session=?',(session,));batch=[]
  def flush():
   if not batch:return
   ys=vectors(db,[r['text'] for r,x,q in batch],encoder);hs=vectors(db,[r['previous'] or ' ' for r,x,q in batch],encoder)
   for (r,x,q),y,h in zip(batch,ys,hs):
    ident=hashlib.sha256(json.dumps([session,r['onset'],r['text']]).encode()).hexdigest()
    db.execute('INSERT OR REPLACE INTO examples VALUES (?,?,?,?,?,?,?,?,?,?)',(ident,session,r['onset'],r['end'],r['text'],r['previous'],blob(x),blob(q),y,h))
   batch.clear();db.commit();memory_check()
  rows=(json.loads(row[0]) for row in db.execute('SELECT body FROM words WHERE session=? ORDER BY onset,id',(session,)))
  for r in phrases(rows):
   try:
    context=(root/r['context_file']).resolve()
    if not context.is_relative_to(root.resolve()):raise ValueError('Context outside private archive')
    with np.load(context,allow_pickle=False) as z:x,q=eeg_summary(z['sequence'],z['quality'],z['positions'])
    if not np.isfinite(x).all() or not np.isfinite(q).all():raise ValueError('Nonfinite context')
   except (OSError,ValueError,KeyError):skipped+=1;continue
   batch.append((r,x,q))
   if len(batch)>=BATCH:flush()
  flush();db.execute('INSERT OR REPLACE INTO sources VALUES (?,?)',(session,signature));db.commit()
 db.execute('DELETE FROM embeddings WHERE vector NOT IN (SELECT y FROM examples UNION SELECT h FROM examples)');db.commit()
 return skipped

def batches(db,where='1',params=(),feature='x'):
 cursor=db.execute(f'SELECT {feature},y FROM examples WHERE {where} ORDER BY onset,id',params)
 while rows:=cursor.fetchmany(BATCH):yield np.array([array(r[0]) for r in rows],float),np.array([array(r[1]) for r in rows],float)

def cumulative_ridge(db,where='1',params=(),feature='x'):
 # Two passes reproduce the existing standardized/clipped ridge objective,
 # without keeping every EEG feature or target embedding in memory.
 n=0;mean=None;m2=None
 for x,y in batches(db,where,params,feature):
  bn=len(x);bm=x.mean(0);bv=((x-bm)**2).sum(0)
  if mean is None:mean=bm;m2=bv;n=bn
  else:
   delta=bm-mean;m2+=bv+delta**2*n*bn/(n+bn);mean+=delta*bn/(n+bn);n+=bn
 if not n:raise ValueError('No eligible training examples')
 scale=np.sqrt(np.maximum(m2/n,0)).clip(.1);xx=None;xy=None
 for x,y in batches(db,where,params,feature):
  a=np.c_[np.clip((x-mean)/scale,-8,8),np.ones(len(x))]
  if xx is None:xx=np.zeros((a.shape[1],a.shape[1]));xy=np.zeros((a.shape[1],y.shape[1]))
  xx+=a.T@a;xy+=a.T@y
 penalty=np.eye(len(xx))*20;penalty[-1,-1]=1e-6
 return (mean,scale,np.linalg.solve(xx+penalty,xy).astype('f')),n

def block_split(db):
 """Stable randomized five-minute blocks; purge overlapping EEG support."""
 db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('evaluation_block_seed',uuid.uuid4().hex));db.commit()
 seed=db.execute("SELECT value FROM metadata WHERE key='evaluation_block_seed'").fetchone()[0]
 def rank(value):return hashlib.sha256((seed+'|'+value).encode()).hexdigest()
 db.create_function('split_rank',1,rank)
 db.executescript('DROP TABLE IF EXISTS temp.eval_split; CREATE TEMP TABLE eval_split(id TEXT PRIMARY KEY,role TEXT,block TEXT); DROP TABLE IF EXISTS temp.test_support; CREATE TEMP TABLE test_support(session TEXT,start REAL,stop REAL);')
 # Absolute time buckets remain fixed as recordings grow; session is part of the key.
 held={}
 for session,onset,end in db.execute('SELECT session,onset,end FROM examples'):
  index=int(onset//300);key=session+':'+str(index)
  if int(rank(key)[:8],16)/2**32<.3:
   lo=index*300-60;hi=max((index+1)*300+1,end+1)
   held[(session,index)]=(lo,max(hi,held.get((session,index),(lo,hi))[1]))
 db.executemany('INSERT INTO test_support VALUES (?,?,?)',[(session,*bounds) for (session,index),bounds in held.items()])
 for ident,session,onset,end in db.execute('SELECT id,session,onset,end FROM examples'):
  index=int(onset//300);key=session+':'+str(index)
  if (session,index) in held:role='test'
  elif db.execute('SELECT 1 FROM test_support WHERE start < ? AND stop > ? LIMIT 1',(end+1,onset-60)).fetchone():role='gap'
  else:role='train'
  db.execute('INSERT INTO eval_split VALUES (?,?,?)',(ident,role,key))
 return seed

def fit_cumulative(root,look,encoder=encode):
 root=Path(root);db=connect(root)
 try:
  skipped=index_archive(root,db,encoder)
  n=db.execute('SELECT count(*) FROM examples').fetchone()[0]
  sessions=db.execute('SELECT session,min(onset),max(end),count(*) FROM examples GROUP BY session ORDER BY min(onset)').fetchall()
  report=dict(kind='semantic',ready=False,provisional=True,cumulative=True,feature_schema=SCHEMA,phrases=n,training_phrases=n,archive_sessions=len(sessions),validation_trials=0,look=look,skipped_records=skipped,reason='Collecting enough independent time blocks for the random-block test.',evaluation_scope='Fixed randomized five-minute time blocks, 30% holdout, purged EEG overlap; live model refit on all indexed phrases.',evaluation_method='random-time-blocks-v1',block_seconds=300,holdout_fraction=.3)
  distinct=db.execute('SELECT count(DISTINCT text) FROM examples').fetchone()[0]
  if n<8 or distinct<4:
   report.update(invalidate_model=True,reason='Need eight eligible phrases with at least four distinct texts.')
   (root/'semantic_checkpoint.npz').unlink(missing_ok=True)
   return None,report
  # The evaluator never fits on held-out blocks or their overlapping EEG context.
  block_split(db)
  where="id IN (SELECT id FROM eval_split WHERE role='train')";params=()
  count=db.execute('SELECT count(*) FROM examples WHERE '+where).fetchone()[0]
  report['embargoed_phrases']=db.execute("SELECT count(*) FROM eval_split WHERE role='gap'").fetchone()[0]
  rows=db.execute("SELECT x,q,y,h,text,session FROM examples e WHERE id IN (SELECT id FROM eval_split WHERE role='test') AND NOT EXISTS (SELECT 1 FROM examples t WHERE t.id IN (SELECT id FROM eval_split WHERE role='train') AND lower(t.text)=lower(e.text)) ORDER BY split_rank(e.id) LIMIT 256").fetchall()
  report['validation_blocks']=db.execute("SELECT count(DISTINCT block) FROM eval_split WHERE role='test'").fetchone()[0]
  if count>=16 and len(rows)>=16 and report['validation_blocks']>=2:
   model,train_n=cumulative_ridge(db,where,params);nuisance,_=cumulative_ridge(db,where,params,'q')
   x=np.array([array(r[0]) for r in rows]);q=np.array([array(r[1]) for r in rows]);y=np.array([array(r[2]) for r in rows]);h=np.array([array(r[3]) for r in rows]);texts=[r[4] for r in rows]
   total=None
   for bx,by in batches(db,where,params):total=by.sum(0) if total is None else total+by.sum(0)
   typical=np.tile(unit(total[None])[0],(len(y),1));pred=apply(model,x);noise=apply(nuisance,q)
   scores=four_choice_scores(pred,y,{'typical':typical,'text_history':h,'signal_quality':noise},texts)
   curve=[]
   for fraction in (.25,.5,1.):
    limit=max(16,int(train_n*fraction));boundary_row=db.execute('SELECT onset FROM examples WHERE '+where+' ORDER BY onset,id LIMIT 1 OFFSET ?',(*params,min(limit,train_n)-1)).fetchone()
    subwhere=where+' AND onset <= ?';subparams=(*params,boundary_row[0]);small,used=cumulative_ridge(db,subwhere,subparams)
    measured=four_choice_scores(apply(small,x),y,{},texts)
    if measured:curve.append(dict(training_phrases=used,accuracy=measured['eeg'],correct=measured['correct'],n=measured['n']))
   report['learning_curve']=dict(points=curve,chance=.25,chance_range=scores['chance_range'] if scores else None,method='Cumulative chronological prefixes; same random-block test phrases. Exploratory; repeated checks are not independent confirmation.')
   report.update(four_choice=scores,validation_trials=len(y),validation_sessions=len(set(r[5] for r in rows)),evaluation_training_phrases=train_n,cosine=float((pred*y).sum(1).mean()),text_history_baseline=float((h*y).sum(1).mean()),mask_baseline=float((noise*y).sum(1).mean()),gain=float(((pred*y).sum(1)-np.maximum.reduce([(typical*y).sum(1),(h*y).sum(1),(noise*y).sum(1)])).mean()),reason='Exploratory random-time-block test with EEG-overlap gaps. The live model uses all data; test scores come from a separate model that excludes held-out blocks.')
  model,trained=cumulative_ridge(db)
  bank=db.execute('SELECT text,y FROM examples ORDER BY onset DESC,id DESC LIMIT 256').fetchall()[::-1]
  target=save_model(root,model,np.array([array(r[1]) for r in bank]),[r[0] for r in bank],look,False)
  report.update(training_phrases=trained,retrieval_library_phrases=len(bank),evaluated_at=time.time(),peak_worker_MB=memory_check()/1e6)
  # This contract is local metadata, not an uploadable contribution.
  contract=dict(schema_version=1,feature_schema=SCHEMA,model_family='standardized-clipped-ridge-v1',participant_scope='one local data directory',local_profile=db.execute("SELECT value FROM metadata WHERE key='local_profile'").fetchone()[0],training_phrases=trained,shared_training_enabled=False,reason='Requires fixed shared normalization, compatible global model, consent and secure aggregation; local checkpoints include private text and must never be uploaded.')
  temp=root/'shared_learning_contract.tmp.json';temp.write_text(json.dumps(contract,indent=2));os.replace(temp,root/'shared_learning_contract.json')
  return target,report
 finally:db.close()
