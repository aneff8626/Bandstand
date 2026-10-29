"""Submit a signed app using a Keychain profile; staple and archive only on acceptance.

No Apple password or API key is accepted as an argument. Configure the profile using
Apple's interactive `xcrun notarytool store-credentials Bandstand` command first.
"""
import argparse,hashlib,json,plistlib,subprocess
from pathlib import Path

def run(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True).stdout

def main():
    p=argparse.ArgumentParser()
    p.add_argument('app',type=Path)
    p.add_argument('--profile',default='Bandstand')
    p.add_argument('--resume',help='Existing submission UUID; do not upload again')
    a=p.parse_args();app=a.app.resolve()
    if app.suffix!='.app' or not (app/'Contents/Info.plist').is_file():p.error('Expected an app bundle')
    run('codesign','--verify','--deep','--strict',str(app))
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    archive=app.parent/f"Bandstand-{info['CFBundleShortVersionString']}-build{info['CFBundleVersion']}-macos-arm64.zip"
    run('xcrun','notarytool','history','--keychain-profile',a.profile,'--output-format','json')
    if a.resume:
        result=json.loads(run('xcrun','notarytool','info',a.resume,'--keychain-profile',a.profile,'--output-format','json'))
    else:
        if archive.exists():archive.unlink()
        run('ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(archive))
        result=json.loads(run('xcrun','notarytool','submit',str(archive),'--keychain-profile',a.profile,'--output-format','json'))
    submission=result['id']
    print('Submission:',submission,'Status:',result.get('status','Submitted'),flush=True)
    (app.parent/'notarization.json').write_text(json.dumps({'id':submission,'status':result.get('status','Submitted')},indent=2))
    if result.get('status')!='Accepted':
        print('Run again with --resume',submission,'after Apple finishes. No acceptance claimed.')
        raise SystemExit(2)
    run('xcrun','stapler','staple',str(app))
    run('xcrun','stapler','validate',str(app))
    run('codesign','--verify','--deep','--strict',str(app))
    run('spctl','--assess','--type','execute','--verbose=2',str(app))
    manifest_path=app.parent/'bundle-manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        manifest['files']={str(p.relative_to(app)):hashlib.sha256(p.read_bytes()).hexdigest() for p in app.rglob('*') if p.is_file()}
        manifest['notarization_id']=submission
        manifest_path.write_text(json.dumps(manifest,indent=2))
    archive.unlink(missing_ok=True)
    run('ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(archive))
    archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    print('Apple accepted; ticket stapled; Gatekeeper assessment passed:',archive)

if __name__=='__main__':main()
