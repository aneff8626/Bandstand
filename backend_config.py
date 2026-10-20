"""One fixed account backend per installation: production unless a validated backend.json ships beside the code.

There is deliberately no environment or runtime override, so a running app cannot be pointed at an
arbitrary upload destination. Development and staging builds place backend.json in the code folder
(inside a signed bundle it is sealed by the signature). The publishable key is not a secret and not an
authorization boundary; secret, service-role and database credentials are rejected outright."""
import json,re,urllib.parse
from pathlib import Path
CODE_ROOT=Path(__file__).resolve().parent
PRODUCTION={'name':'production','url':'https://ovoxgrqhdvzcjqjzgnqk.supabase.co','publishable_key':'sb_publishable_YxUASj1-IWhc9YAo_Qf-hw_NxlqkiJf'}
NAMES=('development','staging')

def validate(config):
 if not isinstance(config,dict) or set(config)!={'name','url','publishable_key'}:
  raise ValueError('backend.json must contain exactly name, url and publishable_key.')
 name,url,key=config['name'],config['url'],config['publishable_key']
 if name not in NAMES:raise ValueError('backend.json name must be development or staging; production is built in.')
 if not isinstance(url,str) or not isinstance(key,str):raise ValueError('backend.json values must be text.')
 parts=urllib.parse.urlsplit(url)
 try:port=parts.port
 except ValueError:raise ValueError('backend.json url has an invalid port.') from None
 hosted=parts.scheme=='https' and re.fullmatch(r'[a-z0-9]{20}\.supabase\.co',parts.hostname or '') is not None and port is None
 # Plain HTTP only to this computer, and only for a development build against a local Supabase stack.
 loopback=parts.scheme=='http' and parts.hostname in ('127.0.0.1','localhost') and port is not None and name=='development'
 if not (hosted or loopback) or parts.path not in ('','/') or parts.query or parts.fragment or parts.username or parts.password:
  raise ValueError('backend.json url must be a Supabase project address (https://<ref>.supabase.co) or, for development, a local stack.')
 base=f'{parts.scheme}://{parts.hostname}'+(f':{port}' if port is not None else '')
 if base==PRODUCTION['url']:raise ValueError('A development or staging build must not target the production project.')
 if not re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]{8,128}',key):
  raise ValueError('backend.json needs the publishable client key. Never place a secret or service-role key in the app.')
 return {'name':name,'url':base,'publishable_key':key}

def load(root=CODE_ROOT):
 path=Path(root)/'backend.json'
 if not path.exists():return dict(PRODUCTION)
 if path.is_symlink():raise ValueError('backend.json must be a regular file.')
 try:config=json.loads(path.read_text())
 except (OSError,UnicodeError,ValueError):raise ValueError('backend.json is unreadable. Account features are disabled; local recording remains available.') from None
 return validate(config)
