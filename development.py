"""Idle-only checkout refresh. Normal bundled/production sessions never enable it."""
import time
from pathlib import Path
import backend_config

class DevelopmentRefresh:
 def __init__(self,root,data_root):
  self.root=Path(root);self.enabled=(backend_config.load(self.root)['name'] in ('development','staging') and Path(data_root).resolve()==(Path.home()/'Library/Application Support/Bandstand Development/data').resolve())
  self.baseline=self.scan() if self.enabled else {};self.current=self.baseline;self.changed_at=0;self.revision=0;self.restart=False
 def scan(self):
  files=list(self.root.glob('*.py'))+list((self.root/'web').rglob('*'))+list((self.root/'native').glob('*.swift'))+[self.root/'requirements.txt',self.root/'backend.json']
  result={}
  for p in files:
   try:
    if p.is_file():
     stat=p.stat();result[str(p.relative_to(self.root))]=(stat.st_mtime_ns,stat.st_size)
   except FileNotFoundError:pass
  return result
 @staticmethod
 def busy(engine):
  return bool((engine.session or {}).get('running') or engine.typing.running or engine.typing.fitting or engine.personal.current or engine.developer.current)
 def status(self,engine):
  if not self.enabled:return {'enabled':False}
  now=self.scan()
  if now!=self.current:self.current=now;self.changed_at=time.monotonic();self.revision+=1
  changes={p for p in now.keys()|self.baseline.keys() if now.get(p)!=self.baseline.get(p)}
  manual=any(p in ('requirements.txt','backend.json') or p.startswith('native/') for p in changes)
  return {'enabled':True,'changed':bool(changes),'revision':self.revision,'css_only':bool(changes) and all(p.endswith('.css') for p in changes),'manual':manual,'settled':time.monotonic()-self.changed_at>=2,'busy':self.busy(engine)}
 def apply(self,engine,revision):
  with engine.lock:
   status=self.status(engine)
   if not status.get('enabled') or not status['changed'] or status['manual'] or not status['settled'] or status['busy'] or revision!=status['revision']:return {'ready':False}
   for p in self.root.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
   self.baseline=self.current.copy();self.restart=not status['css_only']
   return {'ready':True,'restart':self.restart}
