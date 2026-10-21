"""Create a relocatable Apple Silicon development app without participant files."""
from pathlib import Path
import os,sys,shutil,subprocess,plistlib,importlib.metadata as metadata,json,hashlib,re
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import backend_config
VERSION=os.environ.get('BANDSTAND_VERSION','0.3.0')
BUILD=os.environ.get('BANDSTAND_BUILD','13')
if not re.fullmatch(r'\d+\.\d+\.\d+',VERSION) or not re.fullmatch(r'\d+',BUILD):
 raise SystemExit('Use a numeric X.Y.Z version and integer build number.')
# One fixed account backend per installation. Production is built in; a development or staging
# build names a validated backend file explicitly. Validate before any slow work.
BACKEND_FILE=os.environ.get('BANDSTAND_BACKEND_CONFIG','').strip()
BACKEND=backend_config.validate(json.loads(Path(BACKEND_FILE).read_text())) if BACKEND_FILE else None
TARGET=BACKEND['name'] if BACKEND else 'production'
# Persistent certificate signing is required for normal updates. Never silently
# replace a permission-bearing app with a different ad-hoc identity.
SIGN_ID=os.environ.get('BANDSTAND_SIGN_IDENTITY','').strip()
if not SIGN_ID or SIGN_ID=='-':
 raise SystemExit('Set BANDSTAND_SIGN_IDENTITY to a persistent code-signing certificate. Ad-hoc release builds invalidate macOS permissions and are disabled.')
identities=subprocess.run(['/usr/bin/security','find-identity','-v','-p','codesigning'],capture_output=True,text=True,check=True).stdout
if SIGN_ID not in identities:
 raise SystemExit('Requested signing identity is unavailable. Existing application has not been changed.')

subprocess.run([sys.executable,str(ROOT/'scripts/audit_release.py')],check=True,cwd=ROOT)
out=ROOT/'release/Bandstand.app'
if out.exists():shutil.rmtree(out)
resources=out/'Contents/Resources';app=resources/'app';app.mkdir(parents=True)
source=ROOT/'.audit/source'
for p in source.glob('*.py'):shutil.copy2(p,app/p.name)
shutil.copytree(source/'web',app/'web')
for name in ('LICENSE','README.md'):shutil.copy2(source/name,app/name)
(app/'bundled-requirements.txt').write_text((ROOT/'requirements.txt').read_text())
if BACKEND:(app/'backend.json').write_text(json.dumps(BACKEND))
# CPython standalone runtime is relocatable. Exclude all preinstalled packages;
# copy the declared libraries and their platform-specific dependency closure.
base=Path(sys.base_prefix)
def ignore(path,names):return [n for n in names if n in ('site-packages','__pycache__','test','tests','idlelib','tkinter') or n.endswith('.pyc')]
shutil.copytree(base,resources/'python',symlinks=True,ignore=ignore)
# Normalize upstream build-machine symlinks to relocatable sibling targets.
for link in (resources/'python').rglob('*'):
 if link.is_symlink() and link.readlink().is_absolute():
  sibling=link.with_name(link.readlink().name)
  if not sibling.exists():raise ValueError('Unresolved runtime symlink: '+str(link))
  link.unlink();link.symlink_to(sibling.name)
site=resources/'python/lib/python3.12/site-packages';site.mkdir(parents=True,exist_ok=True)
versions={}
pending=['numpy','pillow','reportlab','torch','transformers','cryptography']
while pending:
 name=canonicalize_name(pending.pop())
 if name in versions:continue
 dist=metadata.distribution(name);versions[name]=dist.version
 for requirement in dist.requires or []:
  r=Requirement(requirement)
  if r.marker is None or r.marker.evaluate({'extra':''}):pending.append(r.name)
 for rel in dist.files:
  if '..' in rel.parts or '__pycache__' in rel.parts or str(rel).endswith('.pyc'):continue
  src=Path(dist.locate_file(rel));dst=site/rel
  if src.is_file():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
# Only the immutable public encoder is distributed, never personal checkpoints.
model=Path(os.environ.get('BANDSTAND_PUBLIC_ENCODER',str(ROOT/'models/all-MiniLM-L6-v2')))
verified=json.loads((model/'public-manifest.json').read_text())
for name,digest in verified.items():
 rel=Path(name)
 if rel.is_absolute() or '..' in rel.parts or not re.fullmatch(r'[0-9a-f]{64}',digest):raise ValueError('Invalid public model manifest entry')
 p=model/name
 if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('Public model hash mismatch: '+name)
 target=app/'models/all-MiniLM-L6-v2'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
info=plistlib.loads((ROOT/'Muse Lab.app/Contents/Info.plist').read_bytes())
info.update(CFBundleName='Bandstand',CFBundleDisplayName='Bandstand',CFBundleShortVersionString=VERSION,CFBundleVersion=BUILD,BandstandDevelopmentSourceSupported=('--development-source' in (ROOT/'native/Desktop.swift').read_text() and 'validator.terminationStatus' in (ROOT/'native/Desktop.swift').read_text()),LSMinimumSystemVersion='14.0')
(out/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
icon=ROOT/'Muse Lab.app/Contents/Resources/MuseLab.icns'
if not icon.exists():
 from PIL import Image
 png=ROOT/'build/app-icon.png';png.parent.mkdir(exist_ok=True)
 approved=ROOT/'assets/branding/book-waves-master.png'
 if approved.exists():shutil.copy2(approved,png)
 else:subprocess.run(['/usr/bin/swift','-module-cache-path',str(ROOT/'build/module-cache'),str(ROOT/'scripts/make_icon.swift'),str(png)],check=True)
 icon.parent.mkdir(parents=True,exist_ok=True);Image.open(png).save(icon,format='ICNS')
shutil.copy2(icon,resources/'MuseLab.icns')
mac=out/'Contents/MacOS';mac.mkdir()
subprocess.run(['/usr/bin/swiftc','-module-cache-path',str(ROOT/'build/module-cache'),str(ROOT/'native/Desktop.swift'),str(ROOT/'native/MuseTransport.swift'),str(ROOT/'native/TypingMonitor.swift'),'-o',str(mac/'MuseLab'),'-framework','AppKit','-framework','WebKit','-framework','CoreBluetooth','-framework','ApplicationServices','-framework','Carbon'],check=True)
# Use the same certificate and bundle identifier for every update.
from sign_app import sign
sign(out)
subprocess.run([str(resources/'python/bin/python3.12'),'-c','import numpy,PIL,reportlab,ssl; from semantic_decoder import encode; assert encode(["Synthetic packaging test"]).shape == (1,384); print("Bundled runtime and offline encoder passed")'],check=True,cwd=app,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
# Runtime verification can create bytecode caches; seal the final tested bundle.
sign(out)
subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(out)],check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/smoke_development.py'),str(out)],check=True)
manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
(ROOT/'release/bundle-manifest.json').write_text(json.dumps({'version':VERSION,'architecture':'arm64','backend':TARGET,'dependencies':versions,'files':manifest},indent=2))
archive=ROOT/(f'release/Bandstand-{VERSION}-build{BUILD}-macos-arm64.zip' if TARGET=='production' else f'release/Bandstand-{VERSION}-build{BUILD}-{TARGET}-macos-arm64.zip')
if archive.exists():archive.unlink()
subprocess.run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',str(out),str(archive)],check=True)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n')
print(archive)
print('Signature verified. Clean-Mac Gatekeeper/notarization acceptance still required; this is not an installation-pass claim.')
