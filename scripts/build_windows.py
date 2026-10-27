"""Build a relocatable Windows ZIP from audited source and CPython's embedded runtime.
Run on Windows x64; never package a developer venv, local config, or participant data.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = '3.12.10'

def main():
    if sys.platform != 'win32': raise SystemExit('Build on Windows x64 (or use the Windows Preview workflow).')
    subprocess.run([sys.executable, str(ROOT/'scripts/audit_release.py')], cwd=ROOT, check=True)
    source = ROOT/'.audit/source'
    out = ROOT/'release/windows/Bandstand'
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    app = out/'app'; app.mkdir()
    for p in source.glob('*.py'): shutil.copy2(p, app/p.name)
    for folder in ('web', 'assets', 'docs'):
        if (source/folder).exists(): shutil.copytree(source/folder, app/folder)
    shutil.copy2(ROOT/'LICENSE', out/'LICENSE')
    runtime = out/'runtime'; runtime.mkdir()
    archive = ROOT/'release/windows/python-embed.zip'
    urllib.request.urlretrieve(f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip', archive)
    with zipfile.ZipFile(archive) as z: z.extractall(runtime)
    # Explicit paths retain embedded Python's isolation, including for semantic workers.
    (runtime/'python312._pth').write_text('python312.zip\n.\nLib/site-packages\n../app\nimport site\n')
    site = runtime/'Lib/site-packages'; site.mkdir(parents=True)
    subprocess.run([sys.executable,'-m','pip','install','--target',str(site),
        '-r',str(ROOT/'requirements-windows.txt')],check=True)
    model = ROOT/'models/all-MiniLM-L6-v2'
    if not (model/'public-manifest.json').exists():
        subprocess.run([sys.executable,str(ROOT/'scripts/prepare_public_model.py')],check=True)
    manifest=json.loads((model/'public-manifest.json').read_text())
    for name,digest in manifest.items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts or (model/rel).is_symlink():raise ValueError('Invalid public encoder path')
        content=(model/rel).read_bytes()
        if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('Public encoder hash mismatch')
        dest=app/'models/all-MiniLM-L6-v2'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
    (out/'Launch Bandstand.cmd').write_text('@echo off\r\nset PYTHONDONTWRITEBYTECODE=1\r\nstart "" "%~dp0runtime\\pythonw.exe" -X utf8 "%~dp0app\\windows_app.py"\r\n')
    shutil.copy2(ROOT/'docs/windows-preview.md',out/'START-HERE.md')
    runtime_python=runtime/'python.exe'
    subprocess.run([str(runtime_python), '-X', 'utf8', str(app/'windows_app.py'),'--smoke'],check=True,timeout=90)
    # Actually load the bundled encoder offline; imports alone do not prove dependency completeness.
    subprocess.run([str(runtime_python),'-X','utf8','-c','from semantic_decoder import encode; assert encode(["Synthetic smoke sentence"]).shape == (1,384); print("PASS: offline encoder")'],check=True,timeout=120)
    files={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    (out/'bundle-manifest.json').write_text(json.dumps({'platform':'windows-x64','python':PYTHON_VERSION,'files':files},indent=2))
    name=ROOT/'release/Bandstand-windows-x64-preview'
    shutil.make_archive(str(name),'zip',out.parent,out.name)
    zipped=name.with_suffix('.zip')
    zipped.with_suffix('.zip.sha256').write_text(hashlib.sha256(zipped.read_bytes()).hexdigest()+'  '+zipped.name+'\n')
    print(zipped)

if __name__=='__main__': main()
