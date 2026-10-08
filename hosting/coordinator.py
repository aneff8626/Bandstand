"""Deployment scaffold. Research uploads stay fail-closed until privacy review."""
import json,os
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass  # Never log credentials, bodies, or participant identifiers.
 def do_GET(self):
  if self.path!='/health':return self.reply(404,{'error':'Not found'})
  self.reply(200,{'service':'bandstand-coordinator','research_uploads_enabled':False,'aggregation_ready':False})
 def do_POST(self):self.reply(503,{'error':'Research uploads are disabled; protected aggregation is not deployed.'})
 def reply(self,status,body):
  raw=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
