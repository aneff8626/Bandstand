"""JSON-lines service for the native app. No listening sockets."""
import json, os, sys, time, traceback, zipfile
os.umask(0o077)
from private_storage import DATA_ROOT
from server import engine, Handler, TOKEN
from engine import ROOT, dumps
engine.start()

def dispatch(path,body):
    body=body or {}
    if path.startswith('account/'):
        from accounts import account
        return account(path.split('/')[-1],body)
    if path=='enrollment':
        from enrollment import enrollment
        return enrollment(body if body else None)
    if path=='bluetooth_native':
        with engine.lock:
            if body.get('type')=='motion': engine.ingest_motion(body)
            elif body.get('type')=='status':
                engine.live_status=body
                if engine.source=='live':
                    if body.get('state')=='connecting':
                        for rows in engine.motion_samples.values(): rows.clear()
                        from engine import PacketAssembler
                        from analysis import Filters
                        engine.typing.stop('Headset reconnected')
                        if engine.session and engine.session['running']: engine.stop('headset reconnected')
                        engine.assembler=PacketAssembler(engine.ingest); engine.filters=Filters(); engine.notch=Filters(notch_only=True)
                        engine.times.clear(); engine.raw.clear(); engine.filtered.clear(); engine.spectral.clear()
                    engine.status=body
            elif body.get('type')=='packet' and engine.source=='live': engine.assembler.add(body)
        return {}
    if path.startswith('typing/'):return engine.typing_request(path,body)
    if path=='developer/start':
        with engine.lock:
            if engine.typing.running:raise ValueError('Stop typing recording first.')
            if not engine.times or time.time()-engine.times[-1]>1: raise ValueError('Connect a live headset first.')
            return engine.developer.start(body.get('action'),engine.source,bool(engine.session and engine.session['running']))
    if path=='developer/cue':
        with engine.lock: return engine.developer.cue(body)
    if path=='developer/stop':
        with engine.lock: return engine.developer.finish(cancel=(body or {}).get('cancel',engine.developer.current is not None and engine.developer.current['action']!='free_recording'))
    if path=='clock': return {'time':time.time()}
    if path=='bootstrap': return {'token':TOKEN,**engine.catalog()}
    if path=='state': return engine.snapshot()
    if path=='source': engine.switch_source(body['source']); return {'ok':True}
    if path=='start': return engine.begin(body)
    if path=='event': return engine.event(body)
    if path=='stop': return engine.stop(body.get('reason','stopped'))
    if path=='import': return Handler.import_image(None,body)
    if path=='sessions':
        return [{k:s.get(k) for k in ['id','title','source','started','ended','running']} for s in [json.loads(p.read_text()) for p in sorted((DATA_ROOT).glob('*/session.json'),reverse=True)]]
    if path.startswith('results/'):
        parts=path.split('/')
        if len(parts)==4:return engine.result_window(parts[1],parts[2],parts[3])
        view=engine.saved_view(parts[1])
        return {'session':view.session,'analysis':view.analysis()}
    if path.startswith('export/'):
        parts=path.split('/'); kind=parts[1]
        if kind not in ['raw','processed','pdf']: raise ValueError('Unknown export')
        view=engine.saved_view(parts[2]) if len(parts)>2 else engine
        data,mime,name=view.export(kind); directory=DATA_ROOT/'exports'; directory.mkdir(exist_ok=True)
        dest=directory/name; dest.write_bytes(data)
        return {'message':'Saved to '+str(dest),'file':str(dest)}
    if path.startswith('archive/'):
        ident=path.split('/')[-1]
        if not ident or any(c not in '0123456789-abcdef' for c in ident): raise ValueError('Invalid session')
        directory=DATA_ROOT/ident
        if not directory.is_dir(): raise ValueError('Session not found')
        exports=DATA_ROOT/'exports'; exports.mkdir(exist_ok=True); dest=exports/(ident+'.zip')
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
            for p in directory.iterdir():
                if p.is_file(): z.write(p,p.name)
        return {'message':'Saved to '+str(dest),'file':str(dest)}
    raise ValueError('Unknown request')

try:
    for line in sys.stdin:
        try:
            request=json.loads(line)
            result=dispatch(request['path'],request.get('body'))
            if request['id'] >= 0: print(dumps({'id':request['id'],'result':result}),flush=True)
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            print(dumps({'id':request.get('id'),'error':str(e)}),flush=True)
finally:
    engine.typing.stop('Desktop closed')
    engine.developer.finish(cancel=True)
    engine.stop('desktop closed')
    if engine.bridge: engine.bridge.terminate()
