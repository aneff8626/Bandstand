"""Launch an installed signed desktop shell against this editable, staging-only checkout."""
import argparse, subprocess, sys, plistlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import backend_config

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--app',type=Path,default=Path('/Applications/Bandstand.app'));args=parser.parse_args()
 config=backend_config.load(ROOT)
 if config['name']=='production':raise SystemExit('Create a validated development/staging backend.json first. This launcher refuses production.')
 executable=args.app/'Contents/MacOS/MuseLab'
 if not executable.is_file():raise SystemExit('Install the contributor desktop build first.')
 info=plistlib.loads((args.app/'Contents/Info.plist').read_bytes())
 if info.get('BandstandDevelopmentSourceSupported') is not True:
  raise SystemExit('This app is too old for editable-source mode. Install the contributor desktop build; no app was launched.')
 print('Quit other Bandstand windows before launching. Development uses separate local data and requires a contributor build supporting --development-source.')
 subprocess.run(['/usr/bin/open','-n',str(args.app),'--args','--development-source',str(ROOT)],check=True)
if __name__=='__main__':main()
