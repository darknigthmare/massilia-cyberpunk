"""Local-only static server for SOMA//MASSILIA 0.67."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import argparse, webbrowser
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--no-browser',action='store_true');a=p.parse_args()
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
 def end_headers(self): self.send_header('Cache-Control','no-cache');super().end_headers()
try:
 server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
 url=f'http://127.0.0.1:{a.port}/SOMA_MASSILIA_URBAIN_v0_67.html'
 print('SOMA//MASSILIA 0.67 — Quartiers vivants\n'+url+'\nFermer cette fenêtre arrête le serveur.',flush=True)
 if not a.no_browser:webbrowser.open(url)
 server.serve_forever()
except OSError as exc: raise SystemExit(f'Impossible de démarrer le serveur local : {exc}')
except KeyboardInterrupt: pass
