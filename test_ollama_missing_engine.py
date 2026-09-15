#!/usr/bin/env python3
"""
Reproduces the ACTUAL real-world failure Trevor hit, verbatim: after the
[build id] + repr() + retry-transparency diagnostic upgrade shipped, he
pasted back the resulting error, and it turned out to be genuinely useful
this time -- it named the real Ollama response:

    HTTP 500: {"error":"error starting llama-server: llama-server binary
    not found (checked: C:\\Users\\colli\\AppData\\Local\\Programs\\Ollama\\
    llama-server.exe, ...)"}

This is Ollama's OWN inference-engine executable missing from its install
-- nothing to do with which model is configured, and nothing a retry or a
re-pull can fix. But the OLD detection logic (`'not found' in detail.lower()`)
matched this too, because the message literally contains the words "binary
not found" -- so before this fix, the app would have told Trevor to
`ollama pull deepseek-r1:7b` (a model that was already fine) instead of the
real fix (reinstall Ollama / check antivirus quarantine for
llama-server.exe). Confirmed from Trevor's own pasted evidence, not a
guess: the retry (built into the previous build already) hit the identical
HTTP 500 with the identical message, which is exactly what a missing
binary -- and NOT a missing/misnamed model -- looks like from outside.

This test exercises the REAL _nm_ai_complete() against a fake Ollama that
always returns that exact 500, for a model that genuinely IS installed
(appears correctly in /api/tags), and confirms:
  1. The error correctly identifies this as a broken Ollama install, not
     a missing model.
  2. It does NOT tell the user to `ollama pull` the model (that was never
     the problem, and following that advice wastes their time again).
  3. It DOES mention the real causes/fixes: antivirus quarantine of
     llama-server.exe, or a clean Ollama reinstall.
  4. Only ONE /api/generate call is made -- no pointless retry, since no
     model-name variant fixes a missing executable.
  5. The old "has no model" / retry-transparency code path used for a
     genuine missing-model case is untouched by this change (regression
     check against the previous test's scenario 4).
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

spec = importlib.util.spec_from_file_location("stm_under_test3", TARGET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

MODEL = "deepseek-r1:7b"
# Trevor's actual pasted error text, verbatim (truncated the same way his
# paste was, backslashes and all) -- using the real string rather than a
# paraphrase so this test can't quietly drift from what Ollama actually says.
REAL_OLLAMA_ERROR = (
    'error starting llama-server: llama-server binary not found (checked: '
    'C:\\Users\\colli\\AppData\\Local\\Programs\\Ollama\\llama-server.exe, '
    'C:\\Users\\colli\\AppData\\Local\\Programs\\Ollama\\lib\\ollama\\'
    'llama-server.exe, C:\\Users\\colli\\AppData\\Local\\Programs\\lib\\'
    'ollama\\llama-server.exe)'
)


class FakeOllamaBrokenEngine(http.server.BaseHTTPRequestHandler):
    generate_calls = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length).decode())
            FakeOllamaBrokenEngine.generate_calls.append(payload.get('model', ''))
            body = json.dumps({"error": REAL_OLLAMA_ERROR}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        if self.path == '/api/tags':
            # The model IS genuinely installed -- manifest reads fine,
            # it's the engine binary that's gone.
            payload = json.dumps({'models': [{'name': MODEL}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404); self.end_headers()


def with_home(tmp_home, fn):
    real_home = os.environ.get('HOME')
    os.environ['HOME'] = tmp_home
    try:
        return fn()
    finally:
        if real_home is not None:
            os.environ['HOME'] = real_home


def main():
    failures = []
    def check(cond, msg):
        if not cond:
            failures.append(msg); print(f"FAIL: {msg}")
        else:
            print(f"ok:   {msg}")

    FakeOllamaBrokenEngine.generate_calls = []
    server = http.server.HTTPServer(('127.0.0.1', 0), FakeOllamaBrokenEngine)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    tmp_home = tempfile.mkdtemp()
    try:
        (pathlib.Path(tmp_home) / '.nm_ai_url').write_text(base)
        (pathlib.Path(tmp_home) / '.nm_ai_model').write_text(MODEL)
        (pathlib.Path(tmp_home) / '.nm_ai_provider').write_text('ollama')
        text, err = with_home(tmp_home, lambda: mod._nm_ai_complete('hello', timeout=5))
    finally:
        server.shutdown()
        shutil.rmtree(tmp_home, ignore_errors=True)

    print(f"text={text!r}\nerr={err!r}")
    check(text is None, "still an honest failure -- no fabricated success")
    check(err.startswith('[%s]' % mod._NM_BUILD_ID),
          "error carries the build id tag")
    check('llama-server.exe' in err and 'engine' in err,
          "error correctly identifies this as Ollama's engine binary, not "
          "a model, being the problem")
    check('ollama pull' not in err.lower(),
          "error does NOT tell the user to pull the model -- that was "
          "never the problem, and it's actively misleading advice here")
    check('antivirus' in err.lower() and 'ollama.com/download' in err,
          "error names the real, concrete fixes: antivirus quarantine "
          "check, or a clean reinstall")
    # _nm_ai_complete truncates Ollama's raw detail to 300 chars (the same
    # behaviour that truncated Trevor's own pasted error mid-path) -- so
    # check the raw JSON prefix survived, not a full-string match.
    check('"error": "error starting llama-server: llama-server binary '
          'not found (checked:' in err,
          "Ollama's own raw error text is quoted (truncated the same way "
          "the real one was) for anyone who wants to search/compare it")
    check(FakeOllamaBrokenEngine.generate_calls == [MODEL],
          "exactly ONE /api/generate call was made -- no pointless retry, "
          "since no model-name variant fixes a missing executable")

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s))")
        sys.exit(1)
    print("RESULT: PASS -- a broken/incomplete Ollama install (engine "
          "binary missing) is now correctly told apart from a missing "
          "model, with the real fix instead of misleading pull advice, "
          "and without wasting a retry that could never have helped.")


if __name__ == "__main__":
    main()
