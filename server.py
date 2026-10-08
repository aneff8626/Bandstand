#!/usr/bin/env python3
"""Loopback-only application. No network services or accounts required."""
import base64, hashlib, io, json, os, secrets, sys, threading, time, urllib.parse
os.umask(0o077)  # Set before engine imports create any participant files.
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from PIL import Image, ImageOps
import numpy as np
from private_storage import DATA_ROOT
from engine import Engine, ROOT, dumps

TOKEN=secrets.token_urlsafe(32)
engine=Engine()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):
        if args and '/api/state' in str(args[0]): return
        super().log_message(fmt,*args)
    def send(self,status,data,content_type='application/json',filename=None):
        if isinstance(data,str): data=data.encode()
        self.send_response(status); self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        if filename: self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        try:
            path=urllib.parse.urlparse(self.path).path
            if path=='/api/account/status':
                from accounts import account
                return self.send(200,dumps(account('status')))
            if path=='/api/clock': return self.send(200,dumps({'time':time.time()}))
            if path=='/api/bootstrap': return self.send(200,dumps({'token':TOKEN,**engine.catalog()}))
            if path=='/api/state': return self.send(200,dumps(engine.snapshot()))
            if path=='/api/sessions':
                sessions=[]
                for p in sorted((DATA_ROOT).glob('*/session.json'),reverse=True):
                    s=json.loads(p.read_text()); sessions.append({k:s.get(k) for k in ['id','title','source','started','ended','running','mode','protocol']})
                return self.send(200,dumps(sessions))
            if path.startswith('/api/results/'):
                parts=path.split('/')
                if len(parts)==6:return self.send(200,dumps(engine.result_window(parts[3],parts[4],parts[5])))
                view=engine.saved_view(parts[3]); return self.send(200,dumps({'session':view.session,'analysis':view.analysis()}))
            if path.startswith('/api/export/'):
                parts=path.split('/'); kind=parts[3]
                if kind not in ['raw','processed','pdf']: raise ValueError('Unknown export')
                view=engine.saved_view(parts[4]) if len(parts)>4 else engine
                data,mime,name=view.export(kind); return self.send(200,data,mime,name)
            if path.startswith('/api/archive/'):
                import zipfile
                ident=path.rsplit('/',1)[1]
                if not ident or any(c not in '0123456789-abcdef' for c in ident): raise ValueError('Invalid session identifier')
                directory=DATA_ROOT/ident
                if not directory.is_dir(): raise ValueError('Session not found')
                stream=io.BytesIO()
                with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
                    for p in directory.iterdir():
                        if p.is_file(): z.write(p,p.name)
                return self.send(200,stream.getvalue(),'application/zip',ident+'.zip')
            if path=='/api/enrollment':
                from enrollment import enrollment
                return self.send(200,dumps(enrollment()))
            if path.startswith('/stimuli/'):
                file=DATA_ROOT/'stimuli'/Path(path).name
                if not file.exists():file=ROOT/'stimuli'/Path(path).name
                if file.suffix!='.png' or not file.exists(): return self.send(404,'Not found','text/plain')
                return self.send(200,file.read_bytes(),'image/png')
            mapping={'/':'index.html','/style.css':'style.css',**{'/'+p.name:p.name for p in (ROOT/'web').glob('*.js')}}
            if path not in mapping: return self.send(404,'Not found','text/plain')
            file=ROOT/'web'/mapping[path]; mime={'html':'text/html; charset=utf-8','js':'text/javascript','css':'text/css'}[file.suffix[1:]]
            self.send(200,file.read_bytes(),mime)
        except (ValueError,KeyError) as e: self.send(400,dumps({'error':str(e)}))
        except Exception as e:
            import traceback; traceback.print_exc(); self.send(500,dumps({'error':str(e)}))
    def do_POST(self):
        if self.headers.get('X-Muse-Token')!=TOKEN: return self.send(403,dumps({'error':'Reload the local app to obtain a session token'}))
        if not secrets.compare_digest(self.headers.get('X-Muse-Token',''),TOKEN): return self.send(403,'{}')
        origin=self.headers.get('Origin')
        if origin and origin not in ['http://127.0.0.1:8765','http://localhost:8765']: return self.send(403,'{}')
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>24*1024*1024: raise ValueError('Request exceeds 24 MB')
            body=json.loads(self.rfile.read(length) or b'{}'); path=urllib.parse.urlparse(self.path).path
            if path.startswith('/api/account/'):
                from accounts import account
                result=account(path.split('/')[-1],body)
            elif path=='/api/enrollment':
                from enrollment import enrollment
                result=enrollment(body if body else None)
            elif path in ('/api/bluetooth_connect','/api/bluetooth_disconnect'):
                result=engine.bluetooth_connection(path.endswith('bluetooth_connect'))
            elif path=='/api/source': engine.switch_source(body['source']); result={'ok':True}
            elif path.startswith('/api/typing/'):result=engine.typing_request(path[5:],body)
            elif path=='/api/start': result=engine.begin(body)
            elif path=='/api/event': result=engine.event(body)
            elif path=='/api/stop': result=engine.stop(str(body.get('reason','stopped'))[:100])
            elif path=='/api/import': result=self.import_image(body)
            else: return self.send(404,'{}')
            self.send(200,dumps(result))
        except (ValueError,KeyError,TypeError) as e: self.send(400,dumps({'error':str(e)}))
        except Exception as e:
            import traceback; traceback.print_exc(); self.send(500,dumps({'error':str(e)}))
    def import_image(self,b):
        if engine.session and engine.session['running']: raise ValueError('Finish recording before importing assets')
        category=str(b['category']).strip().lower()[:60]; source=str(b.get('source','')).strip(); license_text=str(b.get('license','')).strip()
        if not category or not source or not license_text: raise ValueError('Category, source/publication and license are required')
        raw=base64.b64decode(b['data'],validate=True)
        im=Image.open(io.BytesIO(raw)); im=ImageOps.exif_transpose(im).convert('L'); im.thumbnail((480,480))
        if im.width<64 or im.height<64: raise ValueError('Image is too small')
        canvas=Image.new('L',(512,512),128); canvas.paste(im,((512-im.width)//2,(512-im.height)//2))
        a=np.asarray(canvas,dtype=float)/255; std=a.std()
        if std<.005: raise ValueError('Image has insufficient contrast')
        # Normalize digital luminance and RMS contrast; these are not photometric calibration.
        a=(a-a.mean())*(.18/std)+.5; clipped=float(np.mean((a<0)|(a>1))); a=np.clip(a,0,1)
        digest=hashlib.sha256(raw).hexdigest(); name=digest[:24]+'.png'; (DATA_ROOT/'stimuli').mkdir(exist_ok=True); Image.fromarray(np.uint8(a*255)).save(DATA_ROOT/'stimuli'/name)
        entry=dict(file=name,sha256=digest,category=category,source=source[:1000],license=license_text[:300],original_name=str(b.get('name',''))[:200],width=512,height=512,mean=float(a.mean()),rms_contrast=float(a.std()),clipped_fraction=clipped,processing='Grayscale, aspect-preserving fit in 480px, gray padding to 512px, target mean .5 RMS .18; 8-bit quantization. Not a validated publication stimulus.')
        with engine.lock:
            manifest=engine.manifest()
            if any(x['sha256']==digest for x in manifest): raise ValueError('Duplicate image already imported')
            manifest.append(entry); (DATA_ROOT/'stimuli/manifest.json').write_text(dumps(manifest))
        return entry

if __name__=='__main__':
    os.umask(0o077)
    server=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
    engine.start(); print('Muse Lab ready at http://127.0.0.1:8765',flush=True)
    try: server.serve_forever()
    finally:
        engine.stop('server stopped')
        if engine.bridge: engine.bridge.terminate()
