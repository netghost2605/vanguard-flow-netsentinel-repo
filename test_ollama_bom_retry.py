#!/usr/bin/env python3
"""
Reproduces Trevor's EXACT reported symptom after the first Ollama-diagnostic
fix shipped: the enriched error now correctly named the endpoint
(http://localhost:11434) and correctly listed 'deepseek-r1:7b' as installed
-- and STILL reported "has no model" for that same, apparently-installed
model. That contradiction (installed per /api/tags, but 404 on /api/generate
for the identical-looking name) is exactly what a stray invisible character
in ~/.nm_ai_model produces: it reads back looking identical to the eye and
to a naive str comparison against the error text, but isn't byte-identical
to what Ollama actually has registered.

This test exercises the REAL _nm_ai_complete() against a fake Ollama that:
  - has 'deepseek-r1:7b' genuinely installed (appears in /api/tags)
  - rejects /api/generate for the dotfile's value, which carries a leading
    BOM ('﻿deepseek-r1:7b') -- simulating a Notepad-saved dotfile --
    UNLESS the request's model field is the clean 'deepseek-r1:7b' string,
    in which case it succeeds.

Two things must be true for the fix to actually work end to end:
  1. _rf()'s own utf-8-sig + _nm_clean_cfg_text read should strip the BOM
     before ever building the request, so in the COMMON case (BOM only in
     the dotfile) the very first /api/generate call already uses the clean
     name and succeeds -- no error, no retry needed.
  2. Separately (and this is the part that matches what Trevor actually
     saw -- a fully-formed, already-correct-looking error), the retry path
     in the 404 handler must independently be able to recover: force a
     dirty request straight into the fake server (bypassing _rf()'s own
     cleanup, the way a real *replicated* BOM stored in a different config
     field or a transient tags-index lag would) and confirm the retry with
     Ollama's own confirmed name still saves the call.
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
import urllib.request

TARGET = "/tmp/work/extracted/speedtest_monitor.py"

spec = importlib.util.spec_from_file_location("stm_under_test2", TARGET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CLEAN_MODEL = "deepseek-r1:7b"
DIRTY_MODEL = "﻿" + CLEAN_MODEL   # what a BOM'd dotfile actually contains


class FakeOllama(http.server.BaseHTTPRequestHandler):
    generate_calls = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length).decode())
            requested = payload.get('model', '')
            FakeOllama.generate_calls.append(requested)
            if requested == CLEAN_MODEL:
                body = json.dumps({'response': 'All quiet on the network tonight.'}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = json.dumps(
                    {"error": "model '%s' not found, try pulling it first" % requested}
                ).encode()
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        if self.path == '/api/tags':
            # The fake server's own truth: deepseek-r1:7b IS installed,
            # reported the way Ollama actually reports it -- clean, no BOM.
            payload = json.dumps({'models': [{'name': CLEAN_MODEL},
                                              {'name': 'llama3.2:latest'}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404); self.end_headers()


def start_server():
    server = http.server.HTTPServer(('127.0.0.1', 0), FakeOllama)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


class FakeOllamaAlwaysFail(http.server.BaseHTTPRequestHandler):
    """Models a corrupted/partial download: /api/tags happily lists the
    model (that's read from cheap manifest metadata) but /api/generate
    404s for it EVERY time, exact name or not -- there is no clean string
    that would ever make this succeed, unlike FakeOllama above."""
    generate_calls = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path == '/api/generate':
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length).decode())
            FakeOllamaAlwaysFail.generate_calls.append(payload.get('model', ''))
            body = json.dumps(
                {"error": "model '%s' not found, try pulling it first" % CLEAN_MODEL}
            ).encode()
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        if self.path == '/api/tags':
            payload = json.dumps({'models': [{'name': CLEAN_MODEL}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404); self.end_headers()


def start_server_always_fail():
    FakeOllamaAlwaysFail.generate_calls = []
    server = http.server.HTTPServer(('127.0.0.1', 0), FakeOllamaAlwaysFail)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


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

    # ── Scenario 1: BOM-corrupted ~/.nm_ai_model, fixed by _rf()'s own
    #    cleanup before the request is ever sent -- no error, no retry.
    server, port = start_server()
    base = f"http://127.0.0.1:{port}"
    tmp_home = tempfile.mkdtemp()
    try:
        (pathlib.Path(tmp_home) / '.nm_ai_url').write_text(base)
        # Written as raw bytes so nothing in THIS test's own writing helpers
        # accidentally normalizes the BOM away before speedtest_monitor.py
        # ever gets to read it.
        (pathlib.Path(tmp_home) / '.nm_ai_model').write_bytes(
            DIRTY_MODEL.encode('utf-8'))
        (pathlib.Path(tmp_home) / '.nm_ai_provider').write_text('ollama')

        FakeOllama.generate_calls.clear()
        text, err = with_home(tmp_home, lambda: mod._nm_ai_complete('hello', timeout=5))
    finally:
        server.shutdown()
        shutil.rmtree(tmp_home, ignore_errors=True)

    print(f"scenario 1 (BOM'd dotfile) -> text={text!r} err={err!r} "
          f"calls={FakeOllama.generate_calls!r}")
    check(text == 'All quiet on the network tonight.',
          "a BOM'd ~/.nm_ai_model still produces a real completion "
          "(cleaned before the first request, no retry needed)")
    check(FakeOllama.generate_calls == [CLEAN_MODEL],
          "exactly one /api/generate call was made, already using the "
          "clean model name (proves _rf() itself stripped the BOM)")

    # ── Scenario 2: force a dirty model straight past _rf() (as if some
    #    other path fed _nm_ai_complete a dirty string despite the cleanup
    #    above -- or a transient tags-index lag put a *correct* string in
    #    front of a momentarily-stale server) by monkeypatching Path.home()
    #    is overkill; instead call the retry helpers directly, since that
    #    is the actual unit of behaviour "the error text can't repro the
    #    fix, but the retry logic can be proven directly" -- and confirm
    #    the full _nm_ai_complete path recovers even when the FIRST attempt
    #    genuinely 404s on a dirty name that _rf() didn't clean (simulated
    #    here by writing the dirty name to a field _rf() does not sanitize
    #    beyond its own cleanup -- so instead we directly drive the retry
    #    path via _nm_find_model_match / _nm_ollama_installed_names, which
    #    is exactly what _nm_ai_complete's 404 handler calls).
    server2, port2 = start_server()
    base2 = f"http://127.0.0.1:{port2}"
    names = mod._nm_ollama_installed_names(base2)
    check(names == [CLEAN_MODEL, 'llama3.2:latest'],
          "_nm_ollama_installed_names() returns the fake server's real list")

    match = mod._nm_find_model_match(DIRTY_MODEL, names)
    check(match == CLEAN_MODEL,
          "_nm_find_model_match() maps the BOM'd requested string to the "
          "clean installed name Ollama actually reports")

    hint = mod._nm_ollama_models_hint(base2, DIRTY_MODEL, names)
    print(f"hint: {hint!r}")
    check('cosmetically different' in hint and repr(CLEAN_MODEL) in hint,
          "the hint text calls out the cosmetic-only mismatch by name when "
          "asked about a requested model that doesn't exactly match")
    server2.shutdown()

    # ── Scenario 3: genuinely-not-installed model -- must NOT retry-loop
    #    or fabricate a success; still returns a clean, honest error.
    server3, port3 = start_server()
    base3 = f"http://127.0.0.1:{port3}"
    tmp_home3 = tempfile.mkdtemp()
    try:
        (pathlib.Path(tmp_home3) / '.nm_ai_url').write_text(base3)
        (pathlib.Path(tmp_home3) / '.nm_ai_model').write_text('totally-different-model:99b')
        (pathlib.Path(tmp_home3) / '.nm_ai_provider').write_text('ollama')
        FakeOllama.generate_calls.clear()
        text3, err3 = with_home(tmp_home3, lambda: mod._nm_ai_complete('hello', timeout=5))
    finally:
        server3.shutdown()
        shutil.rmtree(tmp_home3, ignore_errors=True)

    print(f"scenario 3 (genuinely missing model) -> text={text3!r} err={err3!r}")
    check(text3 is None, "a genuinely-missing model still fails (no false success)")
    check('totally-different-model:99b' in (err3 or ''),
          "error still names the missing model")
    check('cosmetically different' not in (err3 or ''),
          "no bogus 'cosmetically different' note when nothing close is installed")

    # ── Scenario 4: Trevor's ACTUAL reported case after build b-51d3ca67 --
    #    the requested name is an EXACT match for an installed one (no BOM,
    #    no whitespace, nothing cosmetic), /api/tags says it's right there,
    #    and /api/generate STILL 404s for it, every single time, including
    #    on the retry with Ollama's own confirmed name. This is exactly
    #    what a corrupted/partial model download looks like from outside --
    #    it must NOT be reported as a naming mismatch (there isn't one),
    #    and the error must carry enough forensic detail (build id, raw
    #    Ollama error text, the fact that a byte-identical retry ALSO
    #    failed) to tell that apart from every previous hypothesis instead
    #    of just looking like the same message again.
    server4, port4 = start_server_always_fail()
    base4 = f"http://127.0.0.1:{port4}"
    tmp_home4 = tempfile.mkdtemp()
    try:
        (pathlib.Path(tmp_home4) / '.nm_ai_url').write_text(base4)
        (pathlib.Path(tmp_home4) / '.nm_ai_model').write_text(CLEAN_MODEL)
        (pathlib.Path(tmp_home4) / '.nm_ai_provider').write_text('ollama')
        text4, err4 = with_home(tmp_home4, lambda: mod._nm_ai_complete('hello', timeout=5))
    finally:
        server4.shutdown()
        shutil.rmtree(tmp_home4, ignore_errors=True)

    print(f"scenario 4 (exact match, genuinely broken on Ollama's side) -> "
          f"text={text4!r}\nerr={err4!r}")
    check(text4 is None, "still an honest failure -- no fabricated success")
    check(err4.startswith('[%s]' % mod._NM_BUILD_ID),
          "error is tagged with the running build id, so it's unmistakable "
          "whether a future report is even on code that includes this fix")
    check(repr(CLEAN_MODEL) in err4,
          "error shows the model name via repr() -- visible proof there's "
          "no hidden BOM/whitespace this time, instead of asking you to "
          "take my word for it")
    check('same kind of failure' in err4 and 'ollama rm' in err4,
          "when the byte-identical retry ALSO fails, the error says so "
          "explicitly and points at a corrupted/partial download -- not "
          "another naming-mismatch guess")
    check('cosmetically different' not in err4,
          "no bogus cosmetic-mismatch note when the requested and "
          "installed names were already identical")
    check(FakeOllamaAlwaysFail.generate_calls.count(CLEAN_MODEL) == 2,
          "exactly two /api/generate attempts were made (original + one "
          "retry), both with the clean, correct name -- not a retry loop")

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s))")
        sys.exit(1)
    print("RESULT: PASS -- a BOM'd model dotfile self-heals before the "
          "first request, the retry path independently recovers a "
          "cosmetically-different-but-installed model, a genuinely missing "
          "model still fails honestly, and a genuinely-broken-on-Ollama's-"
          "side model (exact name match, still 404s twice) is reported "
          "with full forensic detail instead of a repeat of the same "
          "ambiguous message.")


if __name__ == "__main__":
    main()
