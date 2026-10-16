"""Optional participant records: local only, outside exportable session directories."""
import json, os, re, time, uuid
from pathlib import Path

def participant_context(root,action,body,engine):
 directory=Path(root)/'participant-context';directory.mkdir(mode=0o700,parents=True,exist_ok=True)
 if action=='context':
  raw=body.get('fields',{})
  if not isinstance(raw,dict):raise ValueError('Invalid participant details')
  fields={k:str(raw.get(k,''))[:120].strip() for k in ('subject','age','gender','handedness')}
  if fields['age'] and (not fields['age'].isdigit() or not 0<=int(fields['age'])<=120):raise ValueError('Age must be 0–120, or leave it blank')
  forms=body.get('forms',[])
  if not isinstance(forms,list) or len(forms)>3:raise ValueError('Invalid forms')
  from personal import questionnaire,score
  cleaned=[]
  for form in forms:
   kind=form.get('kind');items=questionnaire(kind);answers=form.get('answers',[])
   if not isinstance(answers,list) or len(answers)>len(items) or any(v is not None and (type(v) is not int or not 1<=v<=5) for v in answers):raise ValueError('Invalid form answers')
   record=dict(kind=kind,answers=answers,skipped=bool(form.get('skipped')),measure='self-report; preparation phase; not EEG-locked')
   if len(answers)==len(items) and all(v is not None for v in answers) and not record['skipped']:record['scores']=score(kind,answers)
   cleaned.append(record)
  ident=uuid.uuid4().hex;record=dict(id=ident,created=time.time(),fields=fields,forms=cleaned,local_only=True)
 elif action=='context-link':
  ident=str(body.get('context_id',''))
  if not re.fullmatch('[0-9a-f]{32}',ident):raise ValueError('Invalid context')
  path=directory/(ident+'.json')
  if not path.exists():raise ValueError('Context not found')
  record=json.loads(path.read_text());session=str(body.get('session_id',''));kind=body.get('kind')
  current={'start':engine.session,'typing/start':engine.typing.session,'personal/start':engine.personal.current}.get(kind)
  if not current or current.get('id')!=session:raise ValueError('Recording does not match participant context')
  if record.get('session_id'):raise ValueError('Participant context already linked')
  record.update(session_id=session,recording_kind=kind)
 else:raise ValueError('Unknown participant action')
 path=directory/(ident+'.json');temporary=path.with_suffix('.tmp')
 with open(temporary,'w') as f:os.chmod(temporary,0o600);json.dump(record,f,allow_nan=False)
 os.replace(temporary,path)
 return {'id':ident,'saved':True}
