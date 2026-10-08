"""Build an explicit source-only review bundle and audit without exposing private text."""
import hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from private_storage import DATA_ROOT
out=ROOT/'.audit/source'
if out.exists():shutil.rmtree(out)
out.mkdir(parents=True,exist_ok=True)
allowed=list(ROOT.glob('*.py'))+[ROOT/'README.md',ROOT/'.gitignore',ROOT/'Launch Muse Lab.command',ROOT/'LICENSE',ROOT/'requirements.txt',ROOT/'Muse Lab.app/Contents/Info.plist']
for directory,extensions in [('web',{'.js','.css','.html'}),('native',{'.swift'}),('tests',{'.py','.cjs'}),('scripts',{'.py','.swift'}),('supabase',{'.sql'}),('hosting',{'.py'}),('docs',{'.html'})]:
 allowed.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in extensions)
allowed.extend([ROOT/'hosting/Dockerfile',ROOT/'hosting/.dockerignore',ROOT/'docs/.nojekyll'])
for p in allowed:
 assert not p.is_symlink()
 q=out/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
# Independent content checks: secret patterns, local identity paths, and exact private strings.
patterns=[r'/Users/[A-Za-z0-9_-]+',r'\b(?:sb_secret_|ghp_|github_pat_)[A-Za-z0-9_]+',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
corpus='\n'.join(p.read_text() for p in out.rglob('*') if p.is_file())
findings=[{'type':'sensitive_pattern','pattern':i} for i,pat in enumerate(patterns) if re.search(pat,corpus)]
private_strings=set()
def collect(value):
 if isinstance(value,dict):
  for k,v in value.items():
   if k in ('text','word','phrase','document') and isinstance(v,str) and len(v.strip())>=24:private_strings.add(v.strip())
   elif isinstance(v,(dict,list)):collect(v)
 elif isinstance(value,list):
  for v in value:collect(v)
for p in DATA_ROOT.rglob('*'):
 if not p.is_file():continue
 if p.suffix=='.txt':
  try:
   private_strings.update(line.strip() for line in p.read_text().splitlines() if len(line.strip())>=24)
  except UnicodeError:pass
 if p.suffix in ('.json','.jsonl'):
  try:
   if p.suffix=='.json':collect(json.loads(p.read_text()))
   else:
    for line in p.read_text().splitlines():
     try:collect(json.loads(line))
     except ValueError:pass
  except (ValueError,UnicodeError):pass
hits=sum(s in corpus for s in private_strings)
if hits:findings.append({'type':'private_string_matches','count':hits})
manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
report={'source_files':len(manifest),'private_strings_compared':len(private_strings),'findings':findings,'passed':not findings,'scope':'Explicit source bundle only. No recordings, models, binaries, logs, local config, imported stimuli or unrelated parent documents.'}
(ROOT/'.audit/release-manifest.json').write_text(json.dumps(manifest,indent=2));(ROOT/'.audit/report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report));sys.exit(bool(findings))
