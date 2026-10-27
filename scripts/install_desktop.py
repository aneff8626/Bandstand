"""Install a verified local build, retaining exactly one rollback outside Applications.

Older generated rollback bundles are replaced; participant data is never touched.
"""
import argparse
import plistlib
import shutil
import subprocess
from pathlib import Path

BUNDLE_ID='local.muselab.desktop'
TEAM='XRB42223Z4'

def verify(path):
    if path.is_symlink():raise ValueError('Refusing a symlink app bundle')
    info=plistlib.loads((path/'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier')!=BUNDLE_ID:raise ValueError('Not a Bandstand desktop bundle')
    subprocess.run(['codesign','--verify','--deep','--strict',str(path)],check=True)
    signature=subprocess.run(['codesign','-dv','--verbose=4',str(path)],capture_output=True,text=True,check=True)
    if 'TeamIdentifier='+TEAM not in signature.stderr:raise ValueError('Unexpected signing team')
    return info

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',nargs='?',type=Path,default=Path(__file__).resolve().parents[1]/'release/Bandstand.app')
    args=parser.parse_args();source=args.source.resolve();target=Path('/Applications/Bandstand.app')
    root=Path.home()/'Library/Application Support/Bandstand Updates'
    rollback=root/'Previous.app';stage=root/'Installing.app'
    if root.is_symlink():raise ValueError('Refusing a symlink update directory')
    verify(source)
    if source==target.resolve():raise ValueError('Choose a separate built application')
    if stage.exists():raise ValueError('An unfinished installation exists; inspect Installing.app first')
    if target.exists():verify(target)
    if rollback.exists():verify(rollback)
    root.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ditto',str(source),str(stage)],check=True);verify(stage)
    # Only this fixed, verified generated app bundle is pruned. No recordings/config are here.
    if rollback.exists():shutil.rmtree(rollback)
    if target.exists():target.rename(rollback)
    try:stage.rename(target)
    except Exception:
        if rollback.exists() and not target.exists():rollback.rename(target)
        raise
    print('Installed Bandstand. One previous build retained outside Applications. Reopen to load it.')

if __name__=='__main__':main()
