"""Create a relocatable Apple Silicon development app without participant files."""
from pathlib import Path
import sys,shutil,subprocess,plistlib,importlib.metadata as metadata,json,hashlib
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'scripts/audit_release.py')],check=True,cwd=ROOT)
out=ROOT/'release/Bandstand.app'
if out.exists():shutil.rmtree(out)
resources=out/'Contents/Resources';app=resources/'app';app.mkdir(parents=True)
source=ROOT/'.audit/source'
for p in source.glob('*.py'):shutil.copy2(p,app/p.name)
shutil.copytree(source/'web',app/'web')
for name in ('LICENSE','README.md'):shutil.copy2(source/name,app/name)
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
pending=['numpy','pillow','reportlab','torch','transformers']
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
model=ROOT/'models/all-MiniLM-L6-v2'
verified=json.loads((model/'public-manifest.json').read_text())
for name,digest in verified.items():
 p=model/name
 if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('Public model hash mismatch: '+name)
 target=app/'models/all-MiniLM-L6-v2'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
info=plistlib.loads((ROOT/'Muse Lab.app/Contents/Info.plist').read_bytes())
info.update(CFBundleName='Bandstand',CFBundleDisplayName='Bandstand',CFBundleShortVersionString='0.2.0',CFBundleVersion='2',LSMinimumSystemVersion='14.0')
(out/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
icon=ROOT/'Muse Lab.app/Contents/Resources/MuseLab.icns'
if not icon.exists():
 from PIL import Image
 png=ROOT/'build/app-icon.png';png.parent.mkdir(exist_ok=True)
 subprocess.run(['/usr/bin/swift','-module-cache-path',str(ROOT/'build/module-cache'),str(ROOT/'scripts/make_icon.swift'),str(png)],check=True)
 icon.parent.mkdir(parents=True,exist_ok=True);Image.open(png).save(icon,format='ICNS')
shutil.copy2(icon,resources/'MuseLab.icns')
mac=out/'Contents/MacOS';mac.mkdir()
subprocess.run(['/usr/bin/swiftc','-module-cache-path',str(ROOT/'build/module-cache'),str(ROOT/'native/Desktop.swift'),str(ROOT/'native/MuseTransport.swift'),str(ROOT/'native/TypingMonitor.swift'),'-o',str(mac/'MuseLab'),'-framework','AppKit','-framework','WebKit','-framework','CoreBluetooth','-framework','ApplicationServices','-framework','Carbon'],check=True)
# Ad-hoc signing checks bundle integrity; it is NOT Developer ID notarization.
subprocess.run(['/usr/bin/codesign','--force','--deep','--sign','-',str(out)],check=True)
manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
(ROOT/'release/bundle-manifest.json').write_text(json.dumps({'version':'0.2.0','architecture':'arm64','dependencies':versions,'files':manifest},indent=2))
subprocess.run([str(resources/'python/bin/python3.12'),'-c','import numpy,PIL,reportlab,ssl; from semantic_decoder import encode; assert encode(["Synthetic packaging test"]).shape == (1,384); print("Bundled runtime and offline encoder passed")'],check=True,cwd=app)
archive=ROOT/'release/Bandstand-0.2.0-macos-arm64.zip'
if archive.exists():archive.unlink()
subprocess.run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',str(out),str(archive)],check=True)
print(archive)
