"""Run an installed signed shell against this checkout, with non-production data."""
import argparse, json, plistlib, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import backend_config

def validate_checkout(root):
 for name in ('desktop_service.py','web/index.html','backend.json'):
  if not (root/name).is_file():raise ValueError('Missing '+name+'. Copy backend.development.example.json to backend.json and configure it first.')
 config=backend_config.load(root)
 if config['name'] not in ('development','staging'):raise ValueError('This launcher refuses production.')
 return config

def dependency_warning(root,app):
 bundled=app/'Contents/Resources/app/bundled-requirements.txt'
 current=root/'requirements.txt'
 if not bundled.exists() or current.read_text().strip()!=bundled.read_text().strip():
  print('WARNING: requirements.txt differs from this contributor build. New or changed Python dependencies may need a new signed build.',file=sys.stderr)
 code="""import sys,json,importlib.metadata as m
from packaging.requirements import Requirement
issues=[]
for line in open(sys.argv[1]):
 line=line.strip()
 if not line or line.startswith('#'):continue
 try:
  r=Requirement(line)
  if r.marker and not r.marker.evaluate():continue
  version=m.version(r.name)
  if version not in r.specifier:issues.append(r.name+' bundled '+version+' does not satisfy '+str(r.specifier))
 except Exception as e:issues.append(line+': '+str(e))
print(json.dumps(issues))
"""
 check=subprocess.run([str(app/'Contents/Resources/python/bin/python3.12'),'-I','-B','-c',code,str(current)],capture_output=True,text=True)
 if check.returncode:print('WARNING: could not check bundled dependencies.',file=sys.stderr)
 else:
  for issue in json.loads(check.stdout):print('WARNING: '+issue+'; install an updated contributor build.',file=sys.stderr)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--app',type=Path,default=Path('/Applications/Bandstand.app'));parser.add_argument('--check',action='store_true',help='Validate without launching');args=parser.parse_args()
 try:validate_checkout(ROOT)
 except ValueError as e:raise SystemExit(str(e))
 app=args.app.resolve()
 if not (app/'Contents/MacOS/MuseLab').is_file():raise SystemExit('Install contributor build 8 or later first.')
 info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
 if info.get('BandstandDevelopmentSourceSupported') is not True or int(info.get('CFBundleVersion','0'))<8:raise SystemExit('Install contributor build 8 or later; older builds incorrectly advertised this capability.')
 dependency_warning(ROOT,app)
 if args.check:return
 # Reuse the immutable public encoder; never copy a participant model into the checkout.
 encoder=ROOT/'models/all-MiniLM-L6-v2'
 if not encoder.exists():
  bundled_encoder=app/'Contents/Resources/app/models/all-MiniLM-L6-v2'
  if not bundled_encoder.is_dir():raise SystemExit('Contributor build is missing its public text encoder.')
  encoder.parent.mkdir(parents=True,exist_ok=True)
  if encoder.is_symlink():encoder.unlink()
  encoder.symlink_to(bundled_encoder,target_is_directory=True)
 print('Quit other Bandstand windows first. Opening Bandstand · Development with separate data. Only run trusted checkouts: code uses the desktop app permissions.')
 subprocess.run(['/usr/bin/open','-n',str(app),'--args','--development-source',str(ROOT)],check=True)
if __name__=='__main__':main()
