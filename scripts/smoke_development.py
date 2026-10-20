"""Packaged native-shell smoke: a temporary checkout's marker must render in WKWebView."""
import argparse,json,os,subprocess,tempfile,time
from pathlib import Path

def main():
 parser=argparse.ArgumentParser();parser.add_argument('app',type=Path);a=parser.parse_args();app=a.app.resolve()
 with tempfile.TemporaryDirectory(prefix='bandstand-editable-smoke-') as folder:
  root=Path(folder);(root/'web').mkdir()
  (root/'web/index.html').write_text('<!doctype html><html data-development-marker="checkout-build8"><body>Contributor smoke fixture</body></html>')
  (root/'backend.json').write_text(json.dumps({'name':'development','url':'http://127.0.0.1:54321','publishable_key':'sb_publishable_smoke_fixture_only'}))
  (root/'desktop_service.py').write_text('import sys\nfor line in sys.stdin: pass\n')
  output=root/'result.json'
  # Direct executable launch ensures the tested process can be waited for and closed.
  process=subprocess.Popen([str(app/'Contents/MacOS/MuseLab'),'--development-source',str(root),'--development-smoke-output',str(output)],env={**os.environ,'BANDSTAND_DATA_DIR':str(root/'must-not-be-used')},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  try:
   _,err=process.communicate(timeout=45)
   assert process.returncode==0,err.decode()[-1000:]
   result=json.loads(output.read_text())
   assert result['marker']=='checkout-build8' and not result['error'],result
   assert Path(result['root']).resolve()==root.resolve(),result
   assert result['runtime']==str(app/'Contents/Resources/python/bin/python3.12'),result
   assert result['data']==str(Path.home()/'Library/Application Support/Bandstand Development/data'),result
   assert result['title']=='Bandstand · Development',result
  finally:
   if process.poll() is None:process.terminate();process.wait(timeout=10)
  (root/'backend.json').write_text(json.dumps({'name':'production','url':'https://ovoxgrqhdvzcjqjzgnqk.supabase.co','publishable_key':'sb_publishable_smoke_fixture_only'}))
  rejected=subprocess.run([str(app/'Contents/MacOS/MuseLab'),'--development-source',str(root)],capture_output=True,timeout=15)
  assert rejected.returncode!=0,'Native shell accepted production configuration'
 print('Packaged WKWebView rendered checkout marker; bundled runtime, isolated data and production refusal passed.')
if __name__=='__main__':main()
