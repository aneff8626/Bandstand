import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from windows_app import protected_handler
import private_storage

class WindowsStorageTests(unittest.TestCase):
    def test_windows_data_defaults_outside_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(private_storage.sys,'platform','win32'), patch.dict(os.environ,{'LOCALAPPDATA':folder},clear=True):
                self.assertEqual(private_storage.data_directory(), (Path(folder)/'Bandstand/data').resolve())

class WindowsHTTPTests(unittest.TestCase):
    def setUp(self):
        class Base(BaseHTTPRequestHandler):
            def send(self,code,data):
                self.send_response(code);self.end_headers();self.wfile.write(data.encode())
            def do_GET(self):self.send(200,'{}')
            def do_POST(self):self.send(200,'{}')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),protected_handler(Base,'test-secret'))
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close()
    def call(self,path='/',headers=None,method='GET'):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request(method,path,headers=headers or {})
        response=connection.getresponse();result=(response.status,dict(response.getheaders()));response.read();connection.close();return result
    def test_launch_cookie_and_protected_reads(self):
        self.assertEqual(self.call('/api/state')[0],403)
        status,headers=self.call('/?launch=test-secret')
        self.assertEqual(status,303);self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        self.assertEqual(self.call('/api/state',{'Cookie':'bandstand_session=test-secret'})[0],200)
    def test_wrong_origin_host_and_key_denied(self):
        for headers in [{'Cookie':'bandstand_session=wrong'},
                        {'Cookie':'bandstand_session=test-secret','Origin':'https://evil.invalid'},
                        {'Cookie':'bandstand_session=test-secret','Host':'evil.invalid'}]:
            self.assertEqual(self.call('/api/state',headers)[0],403)
            self.assertEqual(self.call('/api/start',headers,'POST')[0],403)
        self.assertEqual(self.call('/?launch=test-secret',{'Host':'evil.invalid'})[0],403)
