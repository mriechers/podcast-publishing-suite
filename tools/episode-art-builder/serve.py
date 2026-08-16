#!/usr/bin/env python3
"""HTTP server for the Wonder Cabinet Episode Art Builder.

Serves static files from public/ and adds two endpoints used by the
-customize flow in the wc-episode-art skill:

  GET  /config          -> {"available": bool, "episode": str}
  POST /save/composite  -> writes JPG body to <imagesDir>/<?filename=...>
  POST /save/credits    -> writes text body to <imagesDir>/<stem>_credits.md
                           (stem derived from ?filename= matching the composite;
                           falls back to credits.md when no filename is supplied)

The writable destination is read at request time from
public/episode-preload/.config.json (written by the skill before launch).
Filenames are sanitized to prevent path traversal.

Usage:
  python3 serve.py [port]   (default port: 8765)

The bind is 127.0.0.1 by design — do not change it. To reach the builder from
another device (the normal case: the operator drives this box over SSH), put the
port on the tailnet instead of widening the bind:

  tailscale serve --bg 8765          # tailnet-only; URL is <node>.<tailnet>.ts.net
  tailscale serve --https=443 off    # tear down when finished

Use `serve`, never `funnel`: the /save/* endpoints write files with no auth, so
the tailnet is the correct blast radius and the public internet is not.
"""

import http.server
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent.resolve()
PUBLIC_DIR = ROOT / "public"
CONFIG_PATH = PUBLIC_DIR / "episode-preload" / ".config.json"


def load_config():
    if not CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
    except (OSError, ValueError):
        return None
    images_dir = cfg.get("imagesDir")
    if not images_dir:
        return None
    cfg["imagesDir"] = Path(images_dir).resolve()
    return cfg


def safe_filename(name: str) -> str | None:
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    return name


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/config":
            cfg = load_config()
            if cfg:
                self._json(200, {"available": True, "episode": cfg.get("episode", "")})
            else:
                self._json(200, {"available": False})
            return
        return super().do_GET()

    def do_POST(self):
        cfg = load_config()
        if not cfg:
            self._json(503, {"error": "No episode configured"})
            return
        images_dir: Path = cfg["imagesDir"]
        if not images_dir.is_dir():
            self._json(500, {"error": f"imagesDir does not exist: {images_dir}"})
            return

        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        if parsed.path == "/save/composite":
            qs = parse_qs(parsed.query)
            requested = qs.get("filename", [""])[0]
            filename = safe_filename(requested)
            if not filename:
                self._json(400, {"error": "Invalid or missing filename"})
                return
            target = images_dir / filename
        elif parsed.path == "/save/credits":
            qs = parse_qs(parsed.query)
            requested = qs.get("filename", [""])[0]
            stem = safe_filename(requested)
            if stem:
                # Strip extension to get the basename (e.g. WC_S01_13_..._optionA.jpg → ..._optionA)
                stem = Path(stem).stem
                target = images_dir / f"{stem}_credits.md"
            else:
                target = images_dir / "credits.md"
        else:
            self._json(404, {"error": "Unknown endpoint"})
            return

        try:
            target.write_bytes(body)
        except OSError as e:
            self._json(500, {"error": str(e)})
            return

        self._json(200, {"ok": True, "path": str(target), "bytes": len(body)})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    cfg = load_config()
    print(f"Episode Art Builder on http://127.0.0.1:{port}")
    if cfg:
        print(f"  Episode:    {cfg.get('episode')}")
        print(f"  Images dir: {cfg['imagesDir']}")
    else:
        print("  (no episode configured — preload + save endpoints disabled)")
    http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
