"""Serve SOMA//MASSILIA 0.71 on loopback."""
if __package__:
    from .serve_v68 import main
else:
    from serve_v68 import main

if __name__ == '__main__':
    raise SystemExit(main(document='SOMA_MASSILIA_URBAIN_v0_71.html',
                          edition='SOMA//MASSILIA 0.71 — Marseille augmentée'))
