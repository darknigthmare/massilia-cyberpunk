"""Serve the generated v0.68 game on loopback, without remote dependencies."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import argparse
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = 'SOMA_MASSILIA_URBAIN_v0_68.html'


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


def main(document=DOCUMENT, edition='SOMA//MASSILIA 0.68 — Marseille augmentée'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not (ROOT / document).is_file():
        parser.exit(1, 'HTML absent : lancer python3 lancer.py --prepare-only à la racine.\n')
    try:
        with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
            url = f'http://127.0.0.1:{args.port}/{document}'
            print(f'{edition}\n{url}\nCtrl+C pour arrêter.', flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            server.serve_forever()
    except OSError as error:
        parser.exit(1, f'Impossible de démarrer le serveur local : {error}\n')
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
