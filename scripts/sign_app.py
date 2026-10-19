"""Sign updates with a persistent Developer ID identity; reject identity changes."""
import os,re,subprocess,sys
from pathlib import Path

def macho_files(app):
    magics={b'\xfe\xed\xfa\xce',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca',b'\xca\xfe\xba\xbf',b'\xbf\xba\xfe\xca'}
    for p in sorted(app.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if p.is_symlink() or not p.is_file():continue
        with p.open('rb') as f:magic=f.read(4)
        if magic in magics:yield p

def sign(app):
    identity=os.environ.get('BANDSTAND_SIGN_IDENTITY','').strip()
    if not identity or identity=='-':raise SystemExit('Set BANDSTAND_SIGN_IDENTITY to your Developer ID certificate fingerprint.')
    before=subprocess.run(['codesign','-d','-r-',str(app)],capture_output=True,text=True)
    old=before.stdout+before.stderr
    # Sign nested native libraries and executables first. --deep is for verification,
    # not a substitute for explicitly sealing the bundled Python dependency tree.
    command=['codesign','--force','--options','runtime','--timestamp','--sign',identity]
    for binary in macho_files(app):
        subprocess.run(command+[str(binary)],check=True)
    subprocess.run(command+[str(app)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    result=subprocess.run(['codesign','-d','-r-',str(app)],capture_output=True,text=True,check=True)
    after=result.stdout+result.stderr
    def requirement(s):return next((x for x in s.splitlines() if x.startswith('designated =>')),None)
    if requirement(old) and requirement(old)!=requirement(after):
        raise SystemExit('Signing identity changed. Do not install this update without an explicit identity migration.')
    if 'anchor apple generic' not in after:raise SystemExit('Expected Apple certificate-backed identity.')
    print('Certificate signature verified; update identity preserved.' if requirement(old) else 'Certificate signature verified.')
if __name__=='__main__':sign(Path(sys.argv[1]))
