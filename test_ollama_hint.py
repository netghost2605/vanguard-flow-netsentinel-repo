#!/usr/bin/env python3
"""
Exercises the REAL _nm_ai_complete() against a fake local HTTP server that
mimics Ollama's actual behaviour: /api/generate returns 404 "model not
found" for an unknown model, /api/tags lists what IS installed. Confirms
the "has no model" error text now names the endpoint (base) and lists what
that endpoint actually has -- the exact gap that made Trevor's "AI briefing
unavailable (Ollama has no model 'deepseek-r1:7b' ...)" undiagnosable after
he'd already run `ollama pull deepseek-r1:7b` (against a DIFFERENT Ollama
endpoint than the one the app was actually configured to call, most likely
via a stale ~/.nm_ai_url).

No xvfb needed -- this exercises a pure module-level function, no Tk.
"""
import http.server
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import tempfile
import threading

TARGET = "/tmp/work/extracted/speedtest_monitor.py"

spec = importlib.util.spec_from_file_location("stm_under_test", TARGET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeOllama(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path == '/api/generate':
            body = b'{"error":"model \'deepseek-r1:7b\' not found, try pulling it first"}'
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        if self.path == '/api/tags':
            payload = json.dumps({'models': [{'name': 'llama3.2:latest'},
                                              {'name': 'qwen3:8b'}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404); self.end_headers()


def main():
    server = http.server.HTTPServer(('127.0.0.1', 0), FakeOllama)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # _nm_ai_complete reads model/base from dotfiles under Path.home() --
    # point HOME at a scratch dir for the duration of this test so it
    # doesn't touch (or get affected by) the real user's actual dotfiles.
    tmp_home = tempfile.mkdtemp()
    real_home = os.environ.get('HOME')
    os.environ['HOME'] = tmp_home
    try:
        (pathlib.Path(tmp_home) / '.nm_ai_url').write_text(f'http://127.0.0.1:{port}')
        (pathlib.Path(tmp_home) / '.nm_ai_model').write_text('deepseek-r1:7b')
        (pathlib.Path(tmp_home) / '.nm_ai_provider').write_text('ollama')

        text, err = mod._nm_ai_complete('hello', timeout=5)
    finally:
        if real_home is not None:
            os.environ['HOME'] = real_home
        server.shutdown()
        shutil.rmtree(tmp_home, ignore_errors=True)

    failures = []
    def check(cond, msg):
        if not cond:
            failures.append(msg); print(f"FAIL: {msg}")
        else:
            print(f"ok:   {msg}")

    print(f"error text: {err!r}")
    check(text is None, "no completion text on a 404 model-not-found")
    check(f'127.0.0.1:{port}' in (err or ''),
          "error names the actual endpoint queried (base URL)")
    check("deepseek-r1:7b" in (err or ''), "error names the missing model")
    check("llama3.2:latest" in (err or '') and "qwen3:8b" in (err or ''),
          "error lists what IS actually installed at that endpoint")
    check((err or '').count("Installed there:") == 1,
          "the installed-models hint appears exactly once (no double-enrichment "
          "now that EtherApeWindow._ai_complete no longer re-appends it)")

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s))")
        sys.exit(1)
    print("RESULT: PASS -- the 'has no model' error is now fully self-diagnosing: "
          "which Ollama, what it actually has, no duplication.")


if __name__ == "__main__":
    main()
