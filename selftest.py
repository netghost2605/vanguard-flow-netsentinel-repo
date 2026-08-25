#!/usr/bin/env python3
"""
selftest.py — regression harness for speedtest_monitor.py

Purpose
-------
Prove that a refactor changed NOTHING that the user can observe. Every served
page and asset is hashed; if the hashes still match after a change, that change
is behaviour-neutral for the web surface by construction, not by opinion.

Usage
-----
    python selftest.py --baseline     # record the current behaviour as golden
    python selftest.py                # compare against golden, exit 1 on drift
    python selftest.py --update-ok    # re-baseline AFTER an intended change

Exit code is 0 only when every check passes, so it can gate a build.

Design notes
------------
* Static pages/assets are byte-hashed. They are built from string literals and
  were measured to be byte-stable across repeated fetches.
* API routes return live data, so they are checked STRUCTURALLY (status + the
  set of top-level JSON keys) rather than by bytes. Hashing those would produce
  false alarms the moment real traffic exists.
* The desktop check needs a display. It skips cleanly where there isn't one
  rather than reporting a false failure.
* This file never imports for side effects beyond loading the module under
  test, and never writes to speedtest_monitor.py.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "speedtest_monitor.py")
GOLDEN = os.path.join(HERE, "selftest_golden.json")

# Pages and binary assets: built from literals, hashed byte-for-byte.
STATIC_ROUTES = [
    "/", "/3d", "/sankey", "/talkers", "/agents", "/guide", "/monitor", "/vdi",
    "/analytics", "/honeypot", "/threats",
    "/sw.js", "/manifest.webmanifest",
    "/day-map.jpg", "/world-map.jpg", "/radar-map.png", "/sonar.mp3",
    "/icon-192.png", "/icon-512.png",
]

# Live data: compared on shape, not bytes.
API_ROUTES = ["/api/topology3d", "/api/attack_sim", "/api/killswitch",
              "/api/agents", "/api/analysis", "/api/firewall", "/api/honeypot", "/api/threats"]

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def record(name, status, detail=""):
    results.append((name, status, detail))
    icon = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}[status]
    print(f"  [{icon}] {name}{('  — ' + detail) if detail else ''}")


# ── module loading ──────────────────────────────────────────────────────────
def load_module():
    spec = importlib.util.spec_from_file_location("stm_under_test", TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeMonitor:
    """Minimal stand-in so the web server can start without a live capture."""
    config = {"web_bind": "127.0.0.1"}
    data = {"timestamps": [], "download": [], "upload": [], "ping": []}
    _db = None


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ── A. static checks ────────────────────────────────────────────────────────
def check_compiles():
    r = subprocess.run([sys.executable, "-m", "py_compile", TARGET],
                       capture_output=True, text=True)
    if r.returncode == 0:
        record("compiles", PASS)
        return True
    record("compiles", FAIL, r.stderr.strip().splitlines()[-1] if r.stderr else "")
    return False


def check_undefined_names():
    r = subprocess.run([sys.executable, "-m", "pyflakes", TARGET],
                       capture_output=True, text=True)
    if "No module named" in (r.stderr or ""):
        record("undefined names", SKIP, "pyflakes not installed")
        return True
    bad = [l for l in (r.stdout or "").splitlines() if "undefined name" in l]
    if bad:
        record("undefined names", FAIL, f"{len(bad)} found: {bad[0][:70]}")
        return False
    record("undefined names", PASS, "0")
    return True


def check_duplicate_methods():
    import ast
    tree = ast.parse(open(TARGET, encoding="utf-8").read())
    dupes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            seen = {}
            for b in node.body:
                if isinstance(b, ast.FunctionDef):
                    if b.name in seen:
                        dupes.append(f"{node.name}.{b.name}")
                    seen[b.name] = b.lineno
    # Module-level functions were NOT checked, so an accidentally duplicated
    # block of top-level helpers went unnoticed - the later copy silently
    # overrides the earlier one, which is how a fixed function can appear to
    # have no effect at all.
    from collections import Counter
    top = Counter(n.name for n in tree.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    dupes += ["%s() x%d" % (k, v) for k, v in top.items() if v > 1]
    cls = Counter(n.name for n in tree.body if isinstance(n, ast.ClassDef))
    dupes += ["class %s x%d" % (k, v) for k, v in cls.items() if v > 1]
    if dupes:
        record("duplicate definitions", FAIL,
               "%d found: %s" % (len(dupes), ", ".join(dupes[:4])))
        return False
    record("duplicate definitions", PASS, "none")
    return True


def check_attributes():
    """Catch self.foo references that nothing in the file ever defines.

    This exists because a dialog shipped using self._root and self.TXT while the
    class defines self.root and TEXT. A hand-built stub in the test had those
    attributes set, so the runtime test passed and the real button crashed.
    Deliberately permissive — it only flags names that appear NOWHERE as an
    assignment, constant or method, which is the signature of a typo.
    """
    import ast
    import re as _re
    src = open(TARGET, encoding="utf-8").read()
    tree = ast.parse(src)

    known = set(_re.findall(r"self\.(_?[A-Za-z]\w*)\s*=", src))          # self.x = ...
    known |= set(_re.findall(r"setattr\(\s*self\s*,\s*['\"](\w+)", src))
    # Class-level constants via AST, not regex: several are declared
    # semicolon-separated on one line, which a line-anchored pattern misses.
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for b in cls.body:
            targets = []
            if isinstance(b, ast.Assign):
                targets = b.targets
            elif isinstance(b, ast.AnnAssign) and b.target is not None:
                targets = [b.target]
            for t in targets:
                for nn in ast.walk(t):
                    if isinstance(nn, ast.Name):
                        known.add(nn.id)
    for n in ast.walk(tree):                                            # every method name
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            known.add(n.name)
    known |= {"root", "master", "tk", "winfo_children", "after", "destroy",
              "quit", "update", "bind", "config", "configure"}
    # Inherited from BaseHTTPRequestHandler / socketserver — real attributes
    # that are never assigned in this file.
    known |= {"send_response", "send_header", "end_headers", "wfile", "rfile",
              "path", "headers", "command", "client_address", "server",
              "requestline", "request_version", "protocol_version",
              "log_message", "log_error", "close_connection", "connection"}

    # Scan usages via AST so string literals are ignored — the embedded
    # service-worker JS is full of self.addEventListener, which is not Python.
    bad, seen = [], set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "self"):
            if n.attr in known or n.attr in seen:
                continue
            seen.add(n.attr)
            bad.append("self.%s (line %d)" % (n.attr, getattr(n, "lineno", 0)))
    if bad:
        record("attribute references", FAIL, "%d unknown, e.g. %s" % (len(bad), bad[0]))
        for b in bad[1:5]:
            record("  also", FAIL, b)
        return False
    record("attribute references", PASS, "all self.* resolve")
    return True


def check_treeview_styled():
    """Tables must never render with Tk's white default in a dark UI.

    Either the default 'Treeview' style is themed at startup (covering every
    table in the app), or a call passes an explicit style=.
    """
    src = open(TARGET, encoding="utf-8").read()
    themed_default = bool(re.search(
        r"configure\(\s*'Treeview'\s*,[^)]*background", src, re.S))
    if not themed_default:
        record("treeview styling", FAIL,
               "default Treeview style is never themed - tables will be white")
        return False
    record("treeview styling", PASS, "default table style themed at startup")
    return True


def check_table_columns(pages):
    """Every <thead> must have as many <th> as the JS rows emit <td>.

    A silently-failed header edit leaves the columns shifted, which looks
    plausible on screen but labels every value wrongly.
    """
    bad = 0
    checked = 0
    for route, body in pages.items():
        if not body.lstrip().lower().startswith(("<!doctype", "<html")):
            continue
        theads = re.findall(r"<thead><tr>(.*?)</tr></thead>", body, re.S)
        if not theads:
            continue
        # count td-emitting row builders in the page's script blocks
        # Match any row builder, including ones with attributes on <tr>.
        rows = re.findall(r"return\s+'<tr\b.*?</tr>'", body, re.S)
        if len(theads) != len(rows):
            continue          # can't pair them up reliably; skip rather than cry wolf
        # Pair by count, not document order: a page can declare one <thead>
        # statically and build another inside JS, so order is not reliable.
        th_counts = sorted(t.count("<th") for t in theads)
        td_counts = sorted(r.count("<td") for r in rows)
        checked += len(theads)
        if th_counts != td_counts:
            bad += 1
            record("table columns %s" % route, FAIL,
                   "header widths %s vs row widths %s" % (th_counts, td_counts))
    if bad == 0:
        record("table columns", PASS, "%d table(s) aligned" % checked)
    return bad == 0


def check_js_syntax(pages):
    """node --check every <script> block in every served page."""
    if not shutil.which("node"):
        record("javascript syntax", SKIP, "node not installed")
        return True
    total = bad = 0
    for route, body in pages.items():
        if not body.lstrip().lower().startswith(("<!doctype", "<html")):
            continue
        for i, js in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", body, re.S)):
            if not js.strip():
                continue
            total += 1
            tmp = os.path.join(HERE, f"_js_{abs(hash(route))%9999}_{i}.js")
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(js)
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
            os.remove(tmp)
            if r.returncode != 0:
                bad += 1
                record(f"javascript syntax {route}#{i}", FAIL,
                       (r.stderr or "").strip().splitlines()[0][:70])
    if bad == 0:
        record("javascript syntax", PASS, f"{total} script blocks valid")
    return bad == 0


# ── B. served-surface hashing ───────────────────────────────────────────────
def fetch_all(port):
    """Return {route: bytes} for static routes and {route: parsed} for APIs."""
    pages, apis = {}, {}
    base = f"http://127.0.0.1:{port}"
    for route in STATIC_ROUTES:
        try:
            r = urllib.request.urlopen(base + route, timeout=15)
            pages[route] = (r.status, r.read())
        except Exception as e:
            pages[route] = ("ERR", str(e).encode())
    for route in API_ROUTES:
        try:
            r = urllib.request.urlopen(base + route, timeout=15)
            body = r.read()
            try:
                keys = sorted(json.loads(body).keys())
            except Exception:
                keys = ["<not json>"]
            apis[route] = (r.status, keys)
        except Exception as e:
            apis[route] = ("ERR", [str(e)[:40]])
    return pages, apis


def snapshot(pages, apis):
    snap = {"static": {}, "api": {}}
    for route, (status, body) in pages.items():
        snap["static"][route] = {
            "status": status,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    for route, (status, keys) in apis.items():
        snap["api"][route] = {"status": status, "keys": keys}
    return snap


def compare(current, golden):
    ok = True
    for route, cur in current["static"].items():
        old = golden.get("static", {}).get(route)
        if old is None:
            record(f"route {route}", FAIL, "not in baseline (new route?)")
            ok = False
        elif cur["status"] != old["status"]:
            record(f"route {route}", FAIL, f"status {old['status']} -> {cur['status']}")
            ok = False
        elif cur["sha256"] != old["sha256"]:
            record(f"route {route}", FAIL,
                   f"content changed ({old['bytes']} -> {cur['bytes']} bytes)")
            ok = False
        else:
            record(f"route {route}", PASS, f"{cur['bytes']} bytes identical")
    for route in golden.get("static", {}):
        if route not in current["static"]:
            record(f"route {route}", FAIL, "disappeared")
            ok = False
    for route, cur in current["api"].items():
        old = golden.get("api", {}).get(route)
        if old is None:
            record(f"api {route}", FAIL, "not in baseline")
            ok = False
        elif cur["status"] != old["status"] or cur["keys"] != old["keys"]:
            missing = set(old["keys"]) - set(cur["keys"])
            record(f"api {route}", FAIL,
                   f"shape changed; missing keys: {sorted(missing) or 'none'}")
            ok = False
        else:
            record(f"api {route}", PASS, f"{len(cur['keys'])} keys")
    return ok


# ── C. desktop window ───────────────────────────────────────────────────────
def check_honeypot_radar(mod):
    """The radar pane must actually get laid out when toggled on.

    Pack order matters: a table packed with expand=True claims the whole
    cavity, leaving a later-packed canvas 1px wide and never mapped - a
    button that visibly does nothing.
    """
    import tkinter as tk
    try:
        root = tk.Tk(); root.withdraw()
    except Exception as e:
        record("honeypot radar", SKIP, "no display (%s)" % e)
        return True

    def pump(sec):
        end = time.time() + sec
        while time.time() < end:
            root.update(); root.update_idletasks(); time.sleep(0.03)

    def find(x, label):
        for ch in x.winfo_children():
            if ch.winfo_class() == "Button":
                try:
                    if label in ch.cget("text"):
                        return ch
                except Exception:
                    pass
            r = find(ch, label)
            if r:
                return r

    def canv(x):
        for ch in x.winfo_children():
            if ch.winfo_class() == "Canvas":
                return ch
            r = canv(ch)
            if r:
                return r

    try:
        w = mod.EtherApeWindow(tshark_path="/bin/true")
        w._open_honeypot_window()
        tops = [c for c in w.root.winfo_children() if c.winfo_class() == "Toplevel"]
        top = tops[-1]
        pump(1.0)
        btn = find(top, "RADAR")
        if btn is None:
            record("honeypot radar", FAIL, "no RADAR button")
            return False
        btn.invoke(); pump(1.5)
        c = canv(top)
        if c is None or not c.winfo_ismapped() or c.winfo_width() < 60:
            record("honeypot radar", FAIL,
                   "pane not laid out (w=%s mapped=%s)"
                   % (c.winfo_width() if c else None,
                      bool(c.winfo_ismapped()) if c else None))
            return False
        record("honeypot radar", PASS,
               "pane %dx%d, %d items" % (c.winfo_width(), c.winfo_height(),
                                         len(c.find_all())))
        return True
    except Exception as e:
        record("honeypot radar", FAIL, str(e)[:90])
        return False
    finally:
        try: root.destroy()
        except Exception: pass


def check_desktop(mod):
    """Build the real EtherApe window and confirm it constructs and populates."""
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        record("desktop window", SKIP, "no display (run under xvfb-run)")
        return True
    try:
        import tkinter as tk
    except Exception as e:
        record("desktop window", SKIP, f"tkinter unavailable: {e}")
        return True

    # A stub tshark so interface enumeration has something to parse.
    fake = os.path.join(HERE, "_selftest_tshark")
    out = {}
    try:
        if os.name != "nt":
            with open(fake, "w") as fh:
                fh.write('#!/bin/bash\nif [ "$1" == "-D" ]; then\n'
                         '  echo "1. eth0 (Ethernet)"\n  echo "2. wlan0 (Wi-Fi)"\nfi\nexit 0\n')
            os.chmod(fake, 0o755)

        root = tk.Tk()
        root.withdraw()
        w = mod.EtherApeWindow(tshark_path=fake if os.name != "nt" else None)

        def probe():
            try:
                out["ifaces"] = len(w._iface_cb["values"])
                out["built"] = True
            except Exception as e:
                out["err"] = str(e)
            root.quit()

        root.after(4000, probe)
        root.mainloop()
        # Cancel any pending after() callbacks before teardown, otherwise Tk
        # prints "invalid command name" noise that buries real failures.
        try:
            for aid in root.tk.call("after", "info"):
                try:
                    root.after_cancel(aid)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
    except Exception as e:
        record("desktop window", FAIL, f"construction raised: {e}")
        return False
    finally:
        if os.path.exists(fake):
            os.remove(fake)

    if not out.get("built"):
        record("desktop window", FAIL, out.get("err", "did not finish building"))
        return False
    record("desktop window", PASS,
           f"constructed, {out.get('ifaces', 0)} interfaces enumerated")
    return True


# ── main ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true",
                    help="record current behaviour as the golden reference")
    ap.add_argument("--update-ok", action="store_true",
                    help="re-baseline after an intentional change")
    ap.add_argument("--no-desktop", action="store_true",
                    help="skip the desktop window check")
    args = ap.parse_args()
    writing = args.baseline or args.update_ok

    print(f"\nselftest — {os.path.basename(TARGET)} "
          f"({os.path.getsize(TARGET):,} bytes)\n")

    print("static checks")
    ok = check_compiles()
    if not ok:
        print("\nRESULT: FAIL (does not compile — nothing else run)\n")
        return 1
    ok &= check_undefined_names()
    ok &= check_duplicate_methods()
    ok &= check_attributes()

    print("\nserved surface")
    mod = load_module()
    port = free_port()
    srv = mod._ThreeDServer(_FakeMonitor())
    srv._port = port
    threading.Thread(target=srv.serve, daemon=True).start()
    time.sleep(2.5)

    pages, apis = fetch_all(port)
    raw_pages = {r: b.decode("utf-8", "replace") for r, (s, b) in pages.items()}
    current = snapshot(pages, apis)

    if writing:
        with open(GOLDEN, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=2, sort_keys=True)
        for route, info in sorted(current["static"].items()):
            record(f"route {route}", PASS,
                   f"{info['bytes']} bytes  {info['sha256'][:12]}")
        for route, info in sorted(current["api"].items()):
            record(f"api {route}", PASS, f"{len(info['keys'])} keys")
        print(f"\n  baseline written: {os.path.basename(GOLDEN)}")
    else:
        if not os.path.exists(GOLDEN):
            print(f"\nNo baseline found. Run:  python {os.path.basename(__file__)} --baseline\n")
            return 1
        with open(GOLDEN, encoding="utf-8") as fh:
            golden = json.load(fh)
        ok &= compare(current, golden)

    print("\njavascript")
    ok &= check_js_syntax(raw_pages)
    ok &= check_table_columns(raw_pages)
    ok &= check_treeview_styled()

    if not args.no_desktop:
        print("\ndesktop")
        ok &= check_desktop(mod)
    ok &= check_honeypot_radar(mod)

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    n_skip = sum(1 for _, s, _ in results if s == SKIP)
    print(f"\n{'-'*58}")
    print(f"  {n_pass} passed, {n_fail} failed, {n_skip} skipped")
    print(f"  RESULT: {'PASS' if ok and n_fail == 0 else 'FAIL'}")
    print(f"{'-'*58}\n")
    return 0 if (ok and n_fail == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
