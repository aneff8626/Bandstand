"""Windows synthetic-data preview. Runtime and packages are bundled beside the app.
The HTTP service binds only to loopback and requires a per-launch HttpOnly cookie.
No private data or credentials are placed inside the installation folder.
"""
import argparse
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit


def configure(data_root=None):
    os.environ['BANDSTAND_WINDOWS_PREVIEW'] = '1'
    os.environ['MUSE_NATIVE_BLUETOOTH'] = '1'  # Do not launch the macOS transport.
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local') / 'Bandstand Windows Preview'
    # Only smoke tests supply an alternate directory. Never reuse real EEG training data.
    data = Path(data_root) if data_root else root / 'data'
    data.mkdir(parents=True, exist_ok=True)
    os.environ['BANDSTAND_DATA_DIR'] = str(data.resolve())
    return root


def protected_handler(base, secret):
    class ProtectedHandler(base):
        def log_message(self, *args):
            pass  # Do not log URLs, tokens, or participant requests.

        def authorized(self):
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host:
                self.send(403, '{}'); return False
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + host:
                self.send(403, '{}'); return False
            cookie = SimpleCookie()
            try: cookie.load(self.headers.get('Cookie', ''))
            except Exception: pass
            value = cookie.get('bandstand_session')
            if not value or not hmac.compare_digest(value.value, secret):
                self.send(403, '{}'); return False
            return True

        def do_GET(self):
            url = urlsplit(self.path)
            supplied = parse_qs(url.query).get('launch', [''])[0]
            if url.path == '/' and supplied and hmac.compare_digest(supplied, secret):
                if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                    return self.send(403, '{}')
                self.send_response(303)
                self.send_header('Set-Cookie', f'bandstand_session={secret}; HttpOnly; SameSite=Strict; Path=/')
                self.send_header('Location', '/')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if self.authorized(): super().do_GET()

        def do_POST(self):
            if self.authorized(): super().do_POST()
    return ProtectedHandler


def start_service():
    from http.server import ThreadingHTTPServer
    import server
    secret = secrets.token_urlsafe(32)
    service = ThreadingHTTPServer(('127.0.0.1', 0), protected_handler(server.Handler, secret))
    service.daemon_threads = True
    server.engine.switch_source('simulation')
    server.engine.start()
    threading.Thread(target=service.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{service.server_port}/?launch={secret}'
    return service, server.engine, url


def stop_service(service, engine):
    # Stop all acquisition modes before shutting down the local service.
    with engine.lock:
        if engine.typing.running: engine.typing.stop('Application closed')
        if engine.personal.current: engine.personal.finish('Application closed')
        engine.stop('Application closed')
    service.shutdown()
    service.server_close()


def smoke(service, engine, url):
    import http.cookiejar
    import urllib.request
    import urllib.error
    from semantic_decoder import memory_check
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    client.open(url, timeout=20).read()
    base = url.split('/?')[0]
    def get(path): return json.load(client.open(base + '/api/' + path, timeout=20))
    boot = get('bootstrap')
    assert boot['capabilities']['windows_preview']
    def post(path, body):
        request = urllib.request.Request(base + '/api/' + path, data=json.dumps(body).encode(),
            headers={'Content-Type':'application/json','X-Muse-Token':boot['token']})
        return json.load(client.open(request, timeout=20))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        state = get('state')
        if not state['stale']: break
        time.sleep(.25)
    assert state['source'] == 'simulation' and not state['stale'], 'Synthetic stream did not start'
    post('typing/start', {'capture':'editor'})
    assert get('state')['typing']['session']['source'] == 'simulation'
    post('typing/stop', {})
    for path, body in [('bluetooth_connect', {}), ('source', {'source':'live'}), ('typing/start', {'capture':'system'})]:
        try: post(path, body)
        except urllib.error.HTTPError as error: assert error.code == 400
        else: raise AssertionError('Unsupported operation was accepted: ' + path)
    try: urllib.request.urlopen(base + '/api/state', timeout=10)
    except urllib.error.HTTPError as error: assert error.code == 403
    else: raise AssertionError('Unauthenticated request accepted')
    assert memory_check() > 0
    print('PASS: bundled app, authenticated loopback, synthetic stream, local typing, capability guards, memory check')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.smoke:
        import tempfile
        with tempfile.TemporaryDirectory(prefix='bandstand-windows-smoke-') as directory:
            configure(directory)
            service, engine, url = start_service()
            try: smoke(service, engine, url)
            finally: stop_service(service, engine)
        return
    if sys.platform != 'win32': raise SystemExit('This launcher is for Windows.')
    root = configure()
    service = None
    try:
        import webview
        service, engine, url = start_service()
        webview.create_window('Bandstand · Windows Preview · Synthetic EEG', url, width=1280, height=850, min_size=(900,650))
        webview.start(gui='edgechromium', private_mode=True)
    except Exception:
        import traceback
        root.mkdir(parents=True, exist_ok=True)
        (root / 'startup-error.log').write_text(traceback.format_exc(), encoding='utf-8')
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,
            'Bandstand could not start. Install Microsoft Edge WebView2 Runtime if it is missing. '
            'Startup details are in ' + str(root / 'startup-error.log'), 'Bandstand startup', 0x10)
    finally:
        if service: stop_service(service, engine)

if __name__ == '__main__': main()
