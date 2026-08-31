#!/usr/bin/env python3
"""
Vanguard Flow NetSentinel — Client
========================

A standalone client for the Vanguard Flow NetSentinel desktop app. It connects to a
running instance over HTTP (the same API the phone dashboard uses) and gives
you the full picture from another machine.

Design notes
------------
* Talks to the server's documented API only — it never touches the database or
  the capture engine directly, so it works across the network.
* Asks ``/api/capabilities`` on connect and adapts to what that server actually
  offers, rather than assuming a feature exists.
* Charts use matplotlib when available and degrade to text tables when not, so
  the client still runs on a bare Python install.
* Heavy views (3D topology, flow map, full report) are opened in the browser
  because they are WebGL/HTML — the client links to them rather than
  reimplementing them badly.

Usage:  python nm_client.py  [--server http://host:8765]
"""

import sys
import os
import json
import threading
import queue
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime

APP_NAME = "Vanguard Flow NetSentinel — Client"
VERSION = "1.0.0"
DEFAULT_SERVER = "https://localhost:8765"
CONFIG_PATH = Path.home() / ".nm_client.json"
POLL_SECONDS = 5

# ── palette (matches the main app) ───────────────────────────────────────────
BG      = "#040c18"   # matches the main dashboard background
SURFACE = "#0a1828"   # panel / toolbar
RAISE   = "#0d2235"   # cards, entries, buttons
LINE    = "#1a3050"   # borders
INK     = "#c8dff0"   # primary text
MUTED   = "#6a9ab8"   # secondary text
FAINT   = "#2a4060"   # hints / dividers
CYAN    = "#38b8f0"   # primary accent
MINT    = "#38f0a8"   # ok / download
AMBER   = "#ff9f43"   # warning
VIOLET  = "#a371f7"   # upload / secondary
RED     = "#ff4444"   # error / blocked


# Protocol colours, copied verbatim from PROTO_COLORS in the main app so a flow
# is the same colour in the client as it is in the desktop and web views.
PROTO_COLORS = {
    "http": "#2bff5c", "http2": "#b4ff1a", "tls": "#00ffa3", "ssl": "#12d47a",
    "dns": "#ffb300", "mdns": "#ff3ec8", "dhcp": "#ffe600", "dhcpv6": "#ff8c1a",
    "icmp": "#ff2d55", "icmpv6": "#ff7043", "tcp": "#00b3ff", "udp": "#9b4dff",
    "arp": "#00e5e0", "other": "#7f9fbf",
}


def _proto_col(p):
    return PROTO_COLORS.get(str(p or "other").lower(), PROTO_COLORS["other"])

MONO = ("Consolas", 10)
MONO_S = ("Consolas", 9)
MONO_B = ("Consolas", 11, "bold")
SANS = ("Segoe UI", 10)

SEV_COLOUR = {"crit": RED, "critical": RED, "warn": AMBER,
              "warning": AMBER, "info": CYAN}


# ═════════════════════════════════════════════════════════════════════════════
#  Transport
# ═════════════════════════════════════════════════════════════════════════════
class Api:
    """Thin HTTP client for the Vanguard Flow NetSentinel API."""

    # Path to the server's self-signed cert for local TLS trust.
    # Set to None to disable certificate verification (not recommended beyond localhost).
    # Populated automatically by _build_ssl_ctx() when the client connects to an https:// URL.
    ssl_cafile: str = ""

    def __init__(self, base=DEFAULT_SERVER, timeout=12):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.caps = {}
        self.last_error = ""
        self.license_key = ""

    @staticmethod
    def _build_ssl_ctx(cafile: str = ""):
        """Return an ssl.SSLContext that trusts *cafile* (our self-signed cert).
        Falls back to a context that skips verification only for localhost URLs.
        """
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        if cafile:
            import os
            crt = os.path.expandvars(os.path.expanduser(cafile))
            if os.path.isfile(crt):
                ctx.load_verify_locations(cafile=crt)
                ctx.verify_mode = ssl.CERT_REQUIRED
                ctx.check_hostname = True
                return ctx
        # No cafile — disable verification (localhost self-signed fallback)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _headers(self, extra=None):
        h = {"User-Agent": "NMClient/%s" % VERSION}
        if self.license_key:
            h["X-License-Key"] = self.license_key
        if extra:
            h.update(extra)
        return h

    # -- low level ----------------------------------------------------------
    def _url(self, path, params=None):
        u = self.base + path
        if params:
            u += "?" + urllib.parse.urlencode(params)
        return u

    def _ssl_ctx(self):
        """Return an SSL context when base uses https://, else None."""
        if self.base.startswith('https://'):
            return self._build_ssl_ctx(self.__class__.ssl_cafile)
        return None

    def get_raw(self, path, params=None, timeout=None):
        req = urllib.request.Request(self._url(path, params),
                                     headers=self._headers())
        with urllib.request.urlopen(req, timeout=timeout or self.timeout,
                                    context=self._ssl_ctx()) as r:
            return r.read()

    def get(self, path, params=None, timeout=None):
        """GET returning parsed JSON, or None on failure (reason in last_error)."""
        try:
            data = self.get_raw(path, params, timeout)
            self.last_error = ""
            return json.loads(data.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            self.last_error = "HTTP %s on %s" % (e.code, path)
        except Exception as e:
            self.last_error = str(e)
        return None

    def post(self, path, payload=None, timeout=None):
        try:
            body = json.dumps(payload or {}).encode()
            req = urllib.request.Request(
                self._url(path), data=body, method="POST",
                headers=self._headers({"Content-Type": "application/json"}))
            with urllib.request.urlopen(req, timeout=timeout or self.timeout,
                                        context=self._ssl_ctx()) as r:
                raw = r.read().decode("utf-8", "replace")
            self.last_error = ""
            return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            self.last_error = "HTTP %s on %s" % (e.code, path)
        except Exception as e:
            self.last_error = str(e)
        return None

    # -- discovery ----------------------------------------------------------
    def connect(self):
        """Handshake. Prefers /api/capabilities; falls back to /api/mobile_status
        so it still works against an older server that predates capabilities."""
        c = self.get("/api/capabilities", timeout=6)
        if c and c.get("ok"):
            self.caps = c
            return True, "connected"
        s = self.get("/api/mobile_status", timeout=6)
        if s is not None:
            self.caps = {"ok": True, "api": 0, "api_get": [], "api_post": [],
                         "legacy": True}
            return True, "connected (older server — some views unavailable)"
        msg = self.last_error or "no response"
        if "401" in msg:
            msg = "Licence key required or invalid"
        return False, msg

    def has(self, name):
        """Is this GET endpoint available? Unknown servers get the benefit of
        the doubt so the client stays useful against future versions."""
        g = self.caps.get("api_get")
        return True if not g else (name in g)


# ═════════════════════════════════════════════════════════════════════════════
#  Small helpers
# ═════════════════════════════════════════════════════════════════════════════
def load_config():
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text())
    except Exception:
        pass
    return {}


def _apply_ssl_config(cfg: dict) -> None:
    """Wire the ssl_cafile from config into the Api class so all instances
    created after this point trust the server's self-signed certificate."""
    cafile = cfg.get("ssl_cafile", "") or ""
    if not cafile:
        # Try the well-known default: certs/ next to this script
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        default = os.path.join(here, "certs", "netsentinel.crt")
        if os.path.isfile(default):
            cafile = default
    Api.ssl_cafile = cafile


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except Exception:
        pass


def human_bytes(b):
    try:
        b = float(b)
    except Exception:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return "%.1f %s" % (b, unit)
        b /= 1024
    return "%.1f PB" % b


def ago(ts):
    """Seconds-since-epoch -> short relative string."""
    try:
        import time
        s = max(0, time.time() - float(ts))
    except Exception:
        return ""
    if s < 60:
        return "%ds" % int(s)
    if s < 3600:
        return "%dm" % int(s / 60)
    if s < 86400:
        return "%dh" % int(s / 3600)
    return "%dd" % int(s / 86400)


def fmt(v, dp=1):
    try:
        return ("%%.%df" % dp) % float(v)
    except Exception:
        return "-"


# ═════════════════════════════════════════════════════════════════════════════
#  The client window
# ═════════════════════════════════════════════════════════════════════════════
class ClientApp:
    def __init__(self, root, server=None):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.root = root
        self.cfg = load_config()
        _apply_ssl_config(self.cfg)          # wire TLS cert before first Api use
        self.api = Api(server or self.cfg.get("server", DEFAULT_SERVER))
        self.api.license_key = self.cfg.get("license_key", "")
        self.connected = False
        self.q = queue.Queue()
        self._stop = threading.Event()
        self._tabs_built = set()

        root.title("%s %s" % (APP_NAME, VERSION))
        root.configure(bg=BG)
        root.geometry("1180x760")
        root.minsize(900, 600)

        self._style()
        self._build_header()
        self._build_tabs()
        self._build_status()

        root.after(120, self._drain)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.connect_async()

    # -- chrome -------------------------------------------------------------
    def _style(self):
        st = self.ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        # clam draws 3D relief from lightcolor/darkcolor. Left at their defaults
        # they render as light grey lines across a dark UI, so pin them too.
        st.configure("TNotebook", background=BG, borderwidth=0,
                     bordercolor=LINE, lightcolor=BG, darkcolor=BG)
        st.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED,
                     padding=(15, 7), font=MONO,
                     bordercolor=LINE, lightcolor=SURFACE, darkcolor=SURFACE)
        st.map("TNotebook.Tab",
               background=[("selected", RAISE)], foreground=[("selected", CYAN)],
               lightcolor=[("selected", RAISE)], darkcolor=[("selected", RAISE)],
               bordercolor=[("selected", LINE)])
        try:
            st.configure("TNotebook.Tab", focuscolor=SURFACE)
        except Exception:
            pass
        st.configure("Treeview", background=SURFACE, fieldbackground=SURFACE,
                     foreground=INK, borderwidth=0, rowheight=23, font=MONO_S,
                     bordercolor=LINE, lightcolor=SURFACE, darkcolor=SURFACE)
        st.configure("Treeview.Heading", background=RAISE, foreground=MUTED,
                     font=("Consolas", 9, "bold"), relief="flat",
                     bordercolor=LINE, lightcolor=RAISE, darkcolor=RAISE)
        st.map("Treeview", background=[("selected", "#17405e")])
        st.configure("TFrame", background=BG, bordercolor=BG,
                     lightcolor=BG, darkcolor=BG)
        st.configure("TLabel", background=BG, foreground=INK)
        # Scrollbars were never styled, so clam rendered them light grey against
        # the dark UI. Match them to the dashboard panels.
        for _sb in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
            st.configure(_sb, background=RAISE, troughcolor=SURFACE,
                         bordercolor=LINE, arrowcolor=MUTED,
                         lightcolor=RAISE, darkcolor=RAISE, relief="flat")
            st.map(_sb, background=[("active", LINE), ("pressed", CYAN)])

    def _build_header(self):
        tk = self.tk
        bar = tk.Frame(self.root, bg=SURFACE, height=46)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        # Accent rule under the toolbar, as on the main dashboard
        tk.Frame(self.root, bg=CYAN, height=2).pack(fill="x", side="top")

        tk.Label(bar, text="\u25c8", bg=SURFACE, fg=CYAN,
                 font=("Segoe UI", 15)).pack(side="left", padx=(12, 6))
        tk.Label(bar, text="VANGUARD FLOW NETSENTINEL", bg=SURFACE, fg=INK,
                 font=("Consolas", 11, "bold")).pack(side="left")
        tk.Label(bar, text="client", bg=SURFACE, fg=FAINT,
                 font=MONO_S).pack(side="left", padx=(6, 18))

        tk.Label(bar, text="Server", bg=SURFACE, fg=MUTED,
                 font=MONO_S).pack(side="left", padx=(0, 5))
        self.server_var = tk.StringVar(value=self.api.base)
        e = tk.Entry(bar, textvariable=self.server_var, width=34, bg=RAISE,
                     fg=INK, insertbackground=INK, relief="flat", font=MONO_S,
                     highlightthickness=1, highlightbackground=LINE,
                     highlightcolor=CYAN)
        e.pack(side="left", ipady=4)
        e.bind("<Return>", lambda _e: self.connect_async())

        tk.Label(bar, text="Key", bg=SURFACE, fg=MUTED,
                 font=MONO_S).pack(side="left", padx=(12, 5))
        self.license_var = tk.StringVar(value=self.cfg.get("license_key", ""))
        ke = tk.Entry(bar, textvariable=self.license_var, width=30, bg=RAISE,
                      fg=INK, insertbackground=INK, relief="flat", font=MONO_S,
                      highlightthickness=1, highlightbackground=LINE,
                      highlightcolor=CYAN)
        ke.pack(side="left", ipady=4)
        ke.bind("<Return>", lambda _e: self.connect_async())

        self._btn(bar, "Connect", self.connect_async, CYAN).pack(side="left", padx=6)

        self.dot = tk.Label(bar, text="\u25cf", bg=SURFACE, fg=FAINT,
                            font=("Segoe UI", 12))
        self.dot.pack(side="right", padx=(4, 12))
        self.conn_lbl = tk.Label(bar, text="disconnected", bg=SURFACE,
                                 fg=MUTED, font=MONO_S)
        self.conn_lbl.pack(side="right")

    def _btn(self, parent, text, cmd, colour=CYAN, width=None):
        b = self.tk.Button(parent, text=text, command=cmd, bg=RAISE, fg=colour,
                           activebackground=LINE, activeforeground=INK,
                           relief="flat", font=MONO_S, cursor="hand2",
                           padx=11, pady=4, borderwidth=0)
        if width:
            b.config(width=width)
        return b

    def _build_tabs(self):
        self.nb = self.ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=9, pady=(9, 0))
        self.tabs = {}
        for key, label in [("dash", "Dashboard"), ("alerts", "Alerts"),
                           ("devices", "Devices"), ("latency", "Latency"),
                           ("quality", "Quality"), ("heatmap", "Heatmap"),
                           ("outages", "Outages"), ("vdi", "VDI"),
                           ("sankey", "Flow Map"), ("honeypot", "Honeypot"),
                           ("firewall", "Firewall"), ("agents", "Agents"),
                           ("analytics", "Analytics"), ("views", "Views & Tools")]:
            f = self.tk.Frame(self.nb, bg=BG)
            self.nb.add(f, text=label)
            self.tabs[key] = f
        self.nb.bind("<<NotebookTabChanged>>", lambda _e: self.refresh_current())

    def _build_status(self):
        self.status = self.tk.StringVar(value="Ready")
        bar = self.tk.Frame(self.root, bg=SURFACE, height=25)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.tk.Label(bar, textvariable=self.status, bg=SURFACE, fg=MUTED,
                      font=MONO_S, anchor="w").pack(side="left", padx=11)
        self.tk.Label(bar, text="v%s" % VERSION, bg=SURFACE, fg=FAINT,
                      font=MONO_S).pack(side="right", padx=11)

    # -- threading ----------------------------------------------------------
    def bg(self, fn, *a, **kw):
        """Run a call off the UI thread; results arrive via the queue."""
        def run():
            try:
                fn(*a, **kw)
            except Exception as e:
                self.q.put(("status", "error: %s" % e))
        threading.Thread(target=run, daemon=True).start()

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    import time as _t
                    if _t.time() >= getattr(self, "_sticky_until", 0):
                        self.status.set(payload)
                elif kind == "conn":
                    ok, msg = payload
                    self.connected = ok
                    self.dot.config(fg=MINT if ok else RED)
                    self.conn_lbl.config(text=msg[:46], fg=MINT if ok else RED)
                elif callable(kind):
                    kind(payload)
        except queue.Empty:
            pass
        if not self._stop.is_set():
            self.root.after(200, self._drain)

    # -- connection ---------------------------------------------------------
    def connect_async(self):
        base = self.server_var.get().strip() or DEFAULT_SERVER
        if not base.startswith("http"):
            base = "http://" + base
        _apply_ssl_config(self.cfg)          # re-apply in case server scheme changed
        self.api = Api(base)
        key = self.license_var.get().strip() if hasattr(self, "license_var") \
            else self.cfg.get("license_key", "")
        self.api.license_key = key
        self.cfg["server"] = base
        self.cfg["license_key"] = key
        save_config(self.cfg)
        self.status.set("Connecting to %s ..." % base)

        def work():
            ok, msg = self.api.connect()
            self.q.put(("conn", (ok, msg)))
            self.q.put(("status", "Connected" if ok else "Connection failed: " + msg))
            if ok:
                self.q.put((lambda _: self.refresh_current(), None))
                self.q.put((lambda _: self._schedule_poll(), None))
        self.bg(work)

    def _schedule_poll(self):
        if self._stop.is_set():
            return
        if self.connected:
            self.refresh_current(quiet=True)
        self.root.after(POLL_SECONDS * 1000, self._schedule_poll)

    # -- tab dispatch -------------------------------------------------------
    def refresh_current(self, quiet=False):
        if not self.connected:
            return
        try:
            key = list(self.tabs)[self.nb.index(self.nb.select())]
        except Exception:
            return
        fn = getattr(self, "_load_" + key, None)
        if fn:
            if not quiet:
                self.status.set("Loading %s ..." % key)
            self.bg(fn)

    def _clear(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _unchanged(self, key, payload):
        """True when this tab's data is identical to what is already drawn.

        The 5s poll used to destroy and rebuild every widget on every tick,
        which made the whole window flicker. Most polls return identical data,
        so we hash it and skip the rebuild when nothing moved.
        """
        try:
            import hashlib
            h = hashlib.md5(
                json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        except Exception:
            return False
        if getattr(self, "_hashes", None) is None:
            self._hashes = {}
        same = self._hashes.get(key) == h
        self._hashes[key] = h
        return same and bool(self.tabs[key].winfo_children())

    def _sticky(self, msg, seconds=8):
        """Show a message the background poll is not allowed to overwrite."""
        import time as _t
        self._sticky_until = _t.time() + seconds
        self.status.set(msg)

    def _table(self, parent, cols, widths=None, height=None):
        tv = self.ttk.Treeview(parent, columns=cols, show="headings",
                               height=height or 18)
        for i, c in enumerate(cols):
            tv.heading(c, text=c.upper())
            tv.column(c, width=(widths[i] if widths else 120), anchor="w")
        sb = self.ttk.Scrollbar(parent, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        return tv

    def _stat_row(self, parent, items):
        """items: [(label, value, colour), ...]"""
        row = self.tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(4, 10))
        for label, value, colour in items:
            card = self.tk.Frame(row, bg=SURFACE, highlightthickness=1,
                                 highlightbackground=LINE)
            card.pack(side="left", expand=True, fill="both", padx=4)
            self.tk.Label(card, text=str(value), bg=SURFACE, fg=colour,
                          font=("Consolas", 20, "bold")).pack(anchor="w",
                                                              padx=13, pady=(9, 0))
            self.tk.Label(card, text=label.upper(), bg=SURFACE, fg=FAINT,
                          font=("Consolas", 8)).pack(anchor="w", padx=13, pady=(0, 9))
        return row

    # ── Dashboard ─────────────────────────────────────────────────────────
    def _load_dash(self):
        s = self.api.get("/api/mobile_status")
        h = self.api.get("/api/history", {"range": getattr(self, "_range", "today")})
        self.q.put((lambda _: self._draw_dash(s, h), None))

    def _draw_dash(self, s, h):
        if self._unchanged("dash", (s, h, getattr(self, "_range", "today"))):
            return
        f = self.tabs["dash"]
        self._clear(f)
        if not s or not s.get("ok"):
            self._empty(f, "No data from server")
            return
        c = s.get("current", {}) or {}
        st = (h or {}).get("stats", {}) or {}

        # ── metric cards, laid out like the desktop dashboard ──
        cards = self.tk.Frame(f, bg=BG)
        cards.pack(fill="x", padx=4, pady=(6, 2))
        for label, val, unit, col, key in [
                ("DOWNLOAD", fmt(c.get("download")), "Mbps", CYAN, "download"),
                ("UPLOAD", fmt(c.get("upload")), "Mbps", VIOLET, "upload"),
                ("PING", fmt(c.get("ping"), 1), "ms", AMBER, "ping"),
                ("DNS", fmt(c.get("dns"), 1), "ms", MINT, "dns")]:
            card = self.tk.Frame(cards, bg=SURFACE, highlightthickness=1,
                                 highlightbackground=LINE)
            card.pack(side="left", expand=True, fill="both", padx=4)
            hdr = self.tk.Frame(card, bg=SURFACE)
            hdr.pack(fill="x", padx=13, pady=(9, 0))
            self.tk.Label(hdr, text="\u25c6", bg=SURFACE, fg=col,
                          font=("Segoe UI", 8)).pack(side="left", padx=(0, 5))
            self.tk.Label(hdr, text=label, bg=SURFACE, fg=MUTED,
                          font=("Consolas", 8)).pack(side="left")
            self.tk.Label(card, text=val, bg=SURFACE, fg=col,
                          font=("Consolas", 26, "bold")).pack(anchor="w", padx=13)
            self.tk.Label(card, text=unit, bg=SURFACE, fg=FAINT,
                          font=("Consolas", 8)).pack(anchor="w", padx=13, pady=(0, 4))
            spark = (h or {}).get(key) or []
            self._spark(card, spark, col)

        # ── range chips, as on the main dashboard ──
        chips = self.tk.Frame(f, bg=BG)
        chips.pack(fill="x", padx=8, pady=(8, 2))
        cur = getattr(self, "_range", "today")
        for key, label in [("today", "Today"), ("week", "This Week"),
                           ("month", "This Month"), ("all", "All Time")]:
            on = (key == cur)
            b_ = self.tk.Button(
                chips, text=label, command=lambda k=key: self._set_range(k),
                bg=(RAISE if on else SURFACE), fg=(CYAN if on else MUTED),
                activebackground=RAISE, activeforeground=INK, relief="flat",
                font=MONO_S, cursor="hand2", padx=13, pady=4, borderwidth=0,
                highlightthickness=1,
                highlightbackground=(CYAN if on else LINE))
            b_.pack(side="left", padx=3)
        n = st.get("download", {}).get("n", 0)
        self.tk.Label(chips, text="%d reading%s \u00b7 last %s"
                      % (n, "" if n == 1 else "s", c.get("ts", "\u2014")),
                      bg=BG, fg=FAINT, font=MONO_S).pack(side="right", padx=8)

        # ── charts: download, upload, latency (top) ──
        body = self.tk.Frame(f, bg=BG)
        body.pack(fill="both", expand=True, padx=4, pady=(6, 4))
        ok = self._multi_chart(body, [
            ((h or {}).get("download") or [], "Download  Mbps", CYAN),
            ((h or {}).get("upload") or [], "Upload  Mbps", VIOLET),
            ((h or {}).get("ping") or [], "Latency  ms", AMBER),
            ((h or {}).get("dns") or [], "DNS  ms", MINT)])
        if not ok:
            self._stats_table(body, st)
        else:
            self._stats_table(f, st, compact=True)
        self.q.put(("status", "Dashboard updated \u00b7 %s" % (c.get("ts") or "")))

    def _set_range(self, key):
        self._range = key
        self._hashes = getattr(self, "_hashes", {})
        self._hashes.pop("dash", None)
        self.bg(self._load_dash)

    def _spark(self, parent, series, colour, h=26):
        """Tiny inline trend line under a metric card (no matplotlib needed)."""
        vals = [v for v in series if isinstance(v, (int, float))][-90:]
        cv = self.tk.Canvas(parent, height=h, bg=SURFACE, highlightthickness=0)
        cv.pack(fill="x", padx=13, pady=(0, 10))
        if len(vals) < 2:
            return
        def draw(_e=None):
            cv.delete("all")
            w = max(cv.winfo_width(), 60)
            lo, hi = min(vals), max(vals)
            rng = (hi - lo) or 1.0
            pts = []
            for i, v in enumerate(vals):
                x = i * (w - 2) / (len(vals) - 1) + 1
                y = h - 3 - (v - lo) / rng * (h - 7)
                pts.extend([x, y])
            cv.create_line(*pts, fill=colour, width=1.6, smooth=True)
        cv.bind("<Configure>", draw)
        draw()

    def _stats_table(self, parent, st, compact=False):
        """Avg / Max / Min / sigma table — the same summary the main app shows."""
        if not st:
            return
        box = self.tk.Frame(parent, bg=SURFACE, highlightthickness=1,
                            highlightbackground=LINE)
        box.pack(fill="x", padx=4, pady=(4, 6))
        hdr = ("metric", "avg", "max", "min", "readings")
        for j, htxt in enumerate(hdr):
            self.tk.Label(box, text=htxt.upper(), bg=SURFACE, fg=FAINT,
                          font=("Consolas", 8), anchor="w").grid(
                              row=0, column=j, sticky="ew", padx=12, pady=(7, 3))
        rows = [("Download", "download", CYAN), ("Upload", "upload", VIOLET),
                ("Ping", "ping", AMBER), ("DNS", "dns", MINT)]
        for i, (label, key, col) in enumerate(rows, start=1):
            d = st.get(key, {}) or {}
            for j, val in enumerate([label, fmt(d.get("avg")), fmt(d.get("max")),
                                     fmt(d.get("min")), d.get("n", 0)]):
                self.tk.Label(box, text=val, bg=SURFACE,
                              fg=(col if j == 0 else INK),
                              font=(MONO_S if j else ("Consolas", 9, "bold")),
                              anchor="w").grid(row=i, column=j, sticky="ew",
                                               padx=12, pady=2)
        for j in range(len(hdr)):
            box.columnconfigure(j, weight=1)

    def _multi_chart(self, parent, panels):
        """Grid of charts mirroring the desktop layout. False if no matplotlib."""
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except Exception:
            return False
        fig = Figure(figsize=(12, 5.2), dpi=96, facecolor=BG)
        for i, (series, title, colour) in enumerate(panels):
            ax = fig.add_subplot(2, 2, i + 1, facecolor=SURFACE)
            y = [v for v in series if isinstance(v, (int, float))]
            if y:
                ax.plot(range(len(y)), y, color=colour, lw=1.4)
                ax.fill_between(range(len(y)), y, color=colour, alpha=0.15)
            else:
                ax.text(0.5, 0.5, "no data for this period", color=FAINT,
                        ha="center", va="center", transform=ax.transAxes, fontsize=8)
            ax.set_title(title, color=MUTED, fontsize=8.5, loc="left")
            ax.tick_params(colors=FAINT, labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(LINE)
            ax.grid(True, color=LINE, alpha=0.3, lw=0.5)
        fig.tight_layout(pad=1.4)
        cv = FigureCanvasTkAgg(fig, master=parent)
        cv.draw()
        cv.get_tk_widget().pack(fill="both", expand=True)
        return True

    def _chart(self, parent, series, title, colour):
        """Line chart when matplotlib is available. Returns False if not."""
        if not series:
            self.tk.Label(parent, text="No data for this range", bg=BG,
                          fg=FAINT, font=MONO_S).pack(pady=18)
            return True
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except Exception:
            return False
        fig = Figure(figsize=(9, 3.3), dpi=96, facecolor=BG)
        ax = fig.add_subplot(111, facecolor=SURFACE)
        y = [v for v in series if isinstance(v, (int, float))]
        ax.plot(range(len(y)), y, color=colour, lw=1.5)
        ax.fill_between(range(len(y)), y, color=colour, alpha=0.16)
        ax.set_title(title, color=MUTED, fontsize=9, loc="left")
        ax.tick_params(colors=FAINT, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color(LINE)
        ax.grid(True, color=LINE, alpha=0.35, lw=0.6)
        fig.tight_layout()
        cv = FigureCanvasTkAgg(fig, master=parent)
        cv.draw()
        cv.get_tk_widget().pack(fill="both", expand=True)
        return True

    def _empty(self, frame, msg):
        self.tk.Label(frame, text=msg, bg=BG, fg=FAINT,
                      font=MONO).pack(expand=True, pady=40)

    # ── Alerts ────────────────────────────────────────────────────────────
    def _load_alerts(self):
        d = self.api.get("/api/alerts")
        self.q.put((lambda _: self._draw_alerts(d), None))

    def _draw_alerts(self, d):
        if self._unchanged("alerts", d):
            return
        f = self.tabs["alerts"]
        self._clear(f)
        if not d or not d.get("ok"):
            self._empty(f, "Alerts unavailable")
            return
        bar = self.tk.Frame(f, bg=BG)
        bar.pack(fill="x", pady=(2, 6))
        self.tk.Label(bar, text="%d alert(s) \u00b7 %d unread"
                      % (len(d.get("alerts", [])), d.get("unacked", 0)),
                      bg=BG, fg=MUTED, font=MONO_S).pack(side="left", padx=6)
        self._btn(bar, "Clear all", self._clear_alerts).pack(side="right", padx=4)
        self._btn(bar, "Refresh", lambda: self.bg(self._load_alerts)).pack(side="right")

        tv = self._table(f, ("time", "sev", "kind", "message"),
                         (140, 70, 120, 620))
        for a in d.get("alerts", []):
            sev = str(a.get("sev", "")).lower()
            tv.insert("", "end", values=(
                datetime.fromtimestamp(a.get("ts", 0)).strftime("%d %b %H:%M:%S")
                if a.get("ts") else "",
                sev.upper(), a.get("kind", ""), a.get("msg", "")),
                tags=(sev,))
        for s, col in SEV_COLOUR.items():
            tv.tag_configure(s, foreground=col)
        tv.bind("<Button-3>", lambda e: self._alert_menu(e, tv))
        tv.bind("<Double-1>", lambda e: self._alert_menu(e, tv))
        self.q.put(("status", "Alerts updated"))

    def _alert_ip(self, tv):
        import re
        sel = tv.selection() or tv.identify_row(tv.winfo_pointery()
                                                - tv.winfo_rooty())
        if isinstance(sel, tuple):
            sel = sel[0] if sel else None
        if not sel:
            return None
        vals = tv.item(sel, "values")
        msg = vals[3] if len(vals) > 3 else ""
        ips = re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", msg)
        for p in ips:                       # prefer the public/actionable one
            if not re.match(r"^(10\.|127\.|192\.168\.|169\.254\.|"
                            r"172\.(1[6-9]|2\d|3[01])\.)", p):
                return p
        return ips[0] if ips else None

    def _alert_menu(self, event, tv):
        row = tv.identify_row(event.y)
        if row:
            tv.selection_set(row)
        ip = self._alert_ip(tv)
        if not ip:
            return
        m = self.tk.Menu(tv, tearoff=0)
        m.add_command(label="WHOIS  " + ip, command=lambda: self._whois(ip))
        m.add_command(label="Block  " + ip,
                      command=lambda: self._block(ip, True))
        m.add_command(label="Unblock  " + ip,
                      command=lambda: self._block(ip, False))
        m.add_separator()
        m.add_command(label="Copy IP",
                      command=lambda: (tv.clipboard_clear(),
                                       tv.clipboard_append(ip)))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _clear_alerts(self):
        self.bg(lambda: (self.api.post("/api/ack_alert", {"id": "all"}),
                         self.q.put((lambda _: self.bg(self._load_alerts), None))))

    def _block(self, ip, on):
        def work():
            r = self.api.post("/api/block" if on else "/api/unblock", {"ip": ip})
            ok = bool(r and r.get("ok"))
            self.q.put(("status", ("Blocked " if on else "Unblocked ") + ip
                        if ok else "Failed: " + (self.api.last_error or "unknown")))
        self.bg(work)

    def _whois(self, ip):
        win = self.tk.Toplevel(self.root)
        win.title("WHOIS " + ip)
        win.configure(bg=BG)
        win.geometry("620x480")
        txt = self.tk.Text(win, bg=SURFACE, fg=INK, font=MONO_S, wrap="word",
                           relief="flat", insertbackground=INK)
        txt.pack(fill="both", expand=True, padx=9, pady=9)
        txt.insert("1.0", "Looking up %s ...\n" % ip)
        txt.config(state="disabled")

        def work():
            d = self.api.get("/api/whois", {"ip": ip}, timeout=30)

            def fill(_):
                txt.config(state="normal")
                txt.delete("1.0", "end")
                if not d:
                    txt.insert("end", "Lookup failed: " + self.api.last_error)
                else:
                    s = d.get("summary", {}) or {}
                    if s.get("note"):
                        txt.insert("end", s["note"] + "\n")
                    elif s.get("error"):
                        txt.insert("end", "Error: " + s["error"] + "\n")
                    else:
                        for k in ("org", "netname", "range", "cidr",
                                  "country", "descr"):
                            if s.get(k):
                                txt.insert("end", "%-9s %s\n" % (k + ":", s[k]))
                    if d.get("raw"):
                        txt.insert("end", "\n" + "-" * 56 + "\n" + d["raw"])
                txt.config(state="disabled")
            self.q.put((fill, None))
        self.bg(work)

    # ── Devices ───────────────────────────────────────────────────────────
    def _load_devices(self):
        d = self.api.get("/api/devices")
        self.q.put((lambda _: self._draw_devices(d), None))

    def _draw_devices(self, d):
        if self._unchanged("devices", d):
            return
        f = self.tabs["devices"]
        self._clear(f)
        if not d or not d.get("ok"):
            self._empty(f, "Devices unavailable")
            return
        devs = d.get("devices", [])
        online = sum(1 for x in devs if x.get("online"))
        self._stat_row(f, [("Devices", len(devs), INK),
                           ("Online", online, MINT),
                           ("Offline", len(devs) - online, FAINT)])
        tv = self._table(f, ("name", "ip", "mac", "vendor", "seen"),
                         (230, 130, 165, 250, 90))
        for x in sorted(devs, key=lambda z: not z.get("online")):
            tv.insert("", "end", values=(
                x.get("name") or x.get("hostname") or x.get("vendor") or x.get("ip"),
                x.get("ip", ""), x.get("mac", ""), x.get("vendor", ""),
                ago(x.get("last_seen"))),
                tags=("on" if x.get("online") else "off",))
        tv.tag_configure("on", foreground=INK)
        tv.tag_configure("off", foreground=FAINT)
        self.q.put(("status", "%d devices (%d online)" % (len(devs), online)))

    # ── Latency ───────────────────────────────────────────────────────────
    def _load_latency(self):
        d = self.api.get("/api/latency")
        self.q.put((lambda _: self._draw_latency(d), None))

    def _draw_latency(self, d):
        if self._unchanged("latency", d):
            return
        f = self.tabs["latency"]
        self._clear(f)
        if not d or not d.get("ok"):
            self._empty(f, "Latency unavailable")
            return
        # /api/latency returns {'latest': {target: {target,rtt,loss,jitter,ts}},
        # 'series': {target: [{ts,rtt,loss}, ...]}} — verified against the server.
        latest = d.get("latest", {}) or {}
        rows = list(latest.values()) if isinstance(latest, dict) else list(latest)
        worst = max((r.get("rtt") or 0) for r in rows) if rows else 0
        lossy = sum(1 for r in rows if (r.get("loss") or 0) > 0)
        self._stat_row(f, [("Targets", len(rows), INK),
                           ("Worst RTT ms", fmt(worst, 1),
                            MINT if worst < 50 else (AMBER if worst < 150 else RED)),
                           ("With loss", lossy, RED if lossy else MINT)])
        tv = self._table(f, ("target", "rtt ms", "loss %", "jitter ms", "when"),
                         (260, 110, 110, 120, 150))
        for r in sorted(rows, key=lambda z: -(z.get("rtt") or 0)):
            rtt = r.get("rtt")
            tag = "ok" if (rtt or 0) < 50 else ("warn" if (rtt or 0) < 150 else "bad")
            tv.insert("", "end", values=(
                r.get("target", ""), fmt(rtt), fmt(r.get("loss")),
                fmt(r.get("jitter"), 2), ago(r.get("ts"))), tags=(tag,))
        tv.tag_configure("ok", foreground=INK)
        tv.tag_configure("warn", foreground=AMBER)
        tv.tag_configure("bad", foreground=RED)

        # trend for the busiest target, if the server sent series data
        series = d.get("series", {}) or {}
        if series:
            first = sorted(series.keys())[0]
            pts = [p.get("rtt") for p in series[first]
                   if isinstance(p.get("rtt"), (int, float))]
            if pts:
                body = self.tk.Frame(f, bg=BG)
                body.pack(fill="both", expand=True, pady=(8, 0))
                self._chart(body, pts, "RTT (ms) — %s" % first, CYAN)
        self.q.put(("status", "%d latency target(s)" % len(rows)))

    # ── Quality ───────────────────────────────────────────────────────────
    def _load_quality(self):
        d = self.api.get("/api/quality", {"days": 7}) \
            if self.api.has("quality") else None
        self.q.put((lambda _: self._draw_quality(d), None))

    def _draw_quality(self, d):
        if self._unchanged("quality", d):
            return
        f = self.tabs["quality"]
        self._clear(f)
        if not d or not d.get("ok"):
            self._empty(f, "Quality data unavailable\n"
                           "(needs a server with /api/quality)")
            return
        grade = d.get("grade", "?")
        gcol = MINT if grade in ("A+", "A") else (
            AMBER if grade in ("B", "C") else RED)
        self._stat_row(f, [
            ("Bufferbloat grade", grade, gcol),
            ("Added latency ms", fmt(d.get("bloat_median_ms"), 0), gcol),
            ("Jitter ms", fmt(d.get("jitter_ms"), 2), CYAN),
            ("Loss %", fmt(d.get("loss_pct"), 2), AMBER),
            ("Samples", d.get("samples", 0), MUTED)])
        self.tk.Label(f, text="Grades:  A+ <5ms  \u00b7  A <30ms  \u00b7  B <60ms  "
                              "\u00b7  C <200ms  \u00b7  D <400ms  \u00b7  F 400ms+"
                              "      (latency added while the link is saturated)",
                      bg=BG, fg=FAINT, font=MONO_S).pack(anchor="w", padx=10)
        hist = d.get("history", [])
        body = self.tk.Frame(f, bg=BG)
        body.pack(fill="both", expand=True, padx=4, pady=(8, 0))
        series = [r.get("bloat_ms") for r in hist
                  if isinstance(r.get("bloat_ms"), (int, float))]
        if not self._chart(body, series, "Bufferbloat (ms added under load)", AMBER):
            tv = self._table(body, ("when", "bloat ms", "jitter", "loss %"),
                             (200, 130, 120, 120), height=14)
            for r in hist[-300:]:
                tv.insert("", "end", values=(str(r.get("ts", ""))[:19],
                                             fmt(r.get("bloat_ms")),
                                             fmt(r.get("jitter"), 2),
                                             fmt(r.get("loss_pct"), 2)))
        self.q.put(("status", "Quality: grade %s over %d samples"
                    % (grade, d.get("samples", 0))))

    # ── Heatmap ───────────────────────────────────────────────────────────
    def _load_heatmap(self):
        d = self.api.get("/api/heatmap", {"metric": "download", "days": 90},
                         timeout=30) if self.api.has("heatmap") else None
        self.q.put((lambda _: self._draw_heatmap(d), None))

    def _draw_heatmap(self, d):
        if self._unchanged("heatmap", d):
            return
        f = self.tabs["heatmap"]
        self._clear(f)
        if not d or not d.get("ok"):
            self._empty(f, "Heatmap unavailable\n(needs a server with /api/heatmap)")
            return
        grid = d.get("grid", [])
        labels = d.get("days_labels", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        lo, hi = d.get("scale_min"), d.get("scale_max")
        self.tk.Label(f, text="Median %s by weekday \u00d7 hour \u00b7 last %d days "
                              "\u00b7 %d readings"
                              % (d.get("metric", "download"), d.get("days", 90),
                                 d.get("samples", 0)),
                      bg=BG, fg=MUTED, font=MONO_S).pack(anchor="w", padx=10, pady=(6, 8))

        counts = d.get("counts", [])
        cmin, cmax = d.get("cell_min", []), d.get("cell_max", [])

        # detail strip — filled when a cell is clicked, like the desktop window
        self._hm_detail = self.tk.StringVar(
            value="Click a cell for its sample count and range.")
        self.tk.Label(f, textvariable=self._hm_detail, bg=SURFACE, fg=CYAN,
                      font=MONO_S, anchor="w", padx=10, pady=6).pack(
                          fill="x", padx=10, pady=(0, 8))

        wrap = self.tk.Frame(f, bg=BG)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        # let the grid stretch to fill the window instead of hugging the corner
        for cidx in range(25):
            wrap.columnconfigure(cidx, weight=(0 if cidx == 0 else 1),
                                 minsize=(46 if cidx == 0 else 18))
        for ridx in range(8):
            wrap.rowconfigure(ridx, weight=(0 if ridx == 0 else 1), minsize=18)

        self.tk.Label(wrap, text="", bg=BG).grid(row=0, column=0, sticky="nsew")
        for h in range(24):
            self.tk.Label(wrap, text="%02d" % h, bg=BG, fg=FAINT,
                          font=("Consolas", 8)).grid(row=0, column=h + 1, sticky="nsew")

        def shade(v):
            """Viridis ramp — same scale the desktop heatmap uses."""
            if v is None or lo is None or hi is None or hi <= lo:
                return "#0b1a29"
            t = max(0.0, min(1.0, (v - lo) / (hi - lo)))
            stops = [(0.0, (68, 1, 84)), (0.25, (59, 82, 139)),
                     (0.5, (33, 145, 140)), (0.75, (94, 201, 98)),
                     (1.0, (253, 231, 37))]
            for i in range(len(stops) - 1):
                p, q = stops[i], stops[i + 1]
                if p[0] <= t <= q[0]:
                    k = 0 if q[0] == p[0] else (t - p[0]) / (q[0] - p[0])
                    c = tuple(int(p[1][j] + (q[1][j] - p[1][j]) * k) for j in range(3))
                    return "#%02x%02x%02x" % c
            return "#0b1a29"

        unit = {"download": "Mbps", "upload": "Mbps",
                "ping": "ms", "dns": "ms"}.get(d.get("metric"), "")

        def click(r, c):
            v = grid[r][c] if r < len(grid) and c < len(grid[r]) else None
            day = labels[r] if r < len(labels) else "?"
            if v is None:
                self._hm_detail.set("%s %02d:00  \u2014  no readings in this slot"
                                    % (day, c))
                return
            n = counts[r][c] if r < len(counts) and c < len(counts[r]) else 0
            lo_c = cmin[r][c] if r < len(cmin) and c < len(cmin[r]) else None
            hi_c = cmax[r][c] if r < len(cmax) and c < len(cmax[r]) else None
            rng = ("  \u00b7  range %s\u2013%s" % (fmt(lo_c), fmt(hi_c))) \
                if lo_c is not None and hi_c is not None else ""
            self._hm_detail.set(
                "%s %02d:00  \u2014  median %s %s  \u00b7  %d reading%s%s"
                % (day, c, fmt(v), unit, n, "" if n == 1 else "s", rng))

        best = worst = None
        for r, row in enumerate(grid):
            self.tk.Label(wrap, text=labels[r] if r < len(labels) else "",
                          bg=BG, fg=MUTED, font=MONO_S, anchor="e").grid(
                              row=r + 1, column=0, sticky="nsew", padx=(0, 6))
            for c, v in enumerate(row):
                cell = self.tk.Frame(wrap, bg=shade(v), highlightthickness=1,
                                     highlightbackground=BG, cursor="hand2")
                cell.grid(row=r + 1, column=c + 1, sticky="nsew", padx=1, pady=1)
                cell.bind("<Button-1>", lambda _e, rr=r, cc=c: click(rr, cc))
                cell.bind("<Enter>", lambda _e, rr=r, cc=c: click(rr, cc))
                if v is not None:
                    if best is None or v > best[0]:
                        best = (v, labels[r], c)
                    if worst is None or v < worst[0]:
                        worst = (v, labels[r], c)

        note = "Darker = slower.  Each cell is that weekday and hour across the " \
               "whole window, not just today."
        if best and worst:
            note += "   Best %s %s %02d:00  \u00b7  Worst %s %s %02d:00" % (
                fmt(best[0]), best[1], best[2], fmt(worst[0]), worst[1], worst[2])
        self.tk.Label(f, text=note, bg=BG, fg=FAINT, font=MONO_S,
                      anchor="w").pack(fill="x", padx=10, pady=(2, 8))
        self.q.put(("status", "Heatmap: %s\u2013%s %s"
                    % (lo, hi, d.get("metric", ""))))

    def _tooltip(self, widget, text):
        def enter(_e):
            self.status.set(text)
        widget.bind("<Enter>", enter)

    # ── Outages ───────────────────────────────────────────────────────────
    def _load_outages(self):
        d = self.api.get("/api/outages", {"days": 90}, timeout=30) \
            if self.api.has("outages") else None
        self.q.put((lambda _: self._draw_outages(d), None))

    def _draw_outages(self, d):
        if self._unchanged("outages", d):
            return
        f = self.tabs["outages"]
        self._clear(f)
        if not d or not d.get("ok"):
            self._empty(f, "Outage data unavailable\n(needs a server with /api/outages)")
            return
        s = d.get("stats", {})
        up = s.get("uptime_pct", 100.0)
        self._stat_row(f, [
            ("Outages", s.get("count", 0), RED if s.get("count") else MINT),
            ("Downtime min", fmt(s.get("total_minutes"), 0), AMBER),
            ("Uptime %", fmt(up, 2), MINT if up > 99.5 else AMBER),
            ("Window days", d.get("days", 90), MUTED)])
        tv = self._table(f, ("start", "end", "duration"), (250, 250, 160))
        for o in reversed(d.get("outages", [])):
            mins = o.get("minutes", 0)
            dur = ("%.0f min" % mins) if mins < 90 else ("%.1f h" % (mins / 60.0))
            tv.insert("", "end", values=(o.get("start", "")[:19],
                                         o.get("end", "")[:19], dur))
        self.q.put(("status", "%d outage(s), %.2f%% uptime"
                    % (s.get("count", 0), up)))

    # ── VDI ───────────────────────────────────────────────────────────────
    def _load_vdi(self):
        d = self.api.get("/api/vdi")
        self.q.put((lambda _: self._draw_vdi(d), None))

    def _draw_vdi(self, d):
        if self._unchanged("vdi", d):
            return
        f = self.tabs["vdi"]
        self._clear(f)
        if not d or not d.get("ok"):
            self._empty(f, "VDI data unavailable")
            return
        sess = d.get("sessions", [])
        tv = self._table(f, ("host", "protocol", "rtt ms", "loss %", "health"),
                         (300, 150, 120, 120, 140))
        for s in sess:
            h = str(s.get("health", "")).lower()
            tv.insert("", "end", values=(s.get("host", ""), s.get("proto", ""),
                                         fmt(s.get("rtt_ms")), fmt(s.get("loss_pct")),
                                         h.upper()),
                      tags=(h,))
        tv.tag_configure("good", foreground=MINT)
        tv.tag_configure("fair", foreground=AMBER)
        tv.tag_configure("poor", foreground=RED)
        self.q.put(("status", "%d VDI session(s)" % len(sess)))

    # ── Analytics ─────────────────────────────────────────────────────────
    def _load_analytics(self):
        a = self.api.get("/api/analytics")
        b = self.api.get("/api/briefing")
        self.q.put((lambda _: self._draw_analytics(a, b), None))

    def _draw_analytics(self, a, b):
        if self._unchanged("analytics", (a, b)):
            return
        f = self.tabs["analytics"]
        self._clear(f)
        if not a or not a.get("ok"):
            self._empty(f, "Analytics unavailable")
            return
        sp = a.get("speed", {}) or {}
        self._stat_row(f, [
            ("Avg download", fmt(sp.get("avg_download"), 0), CYAN),
            ("Avg upload", fmt(sp.get("avg_upload"), 0), MINT),
            ("Avg ping", fmt(sp.get("avg_ping"), 0), AMBER),
            ("Uptime %", fmt(a.get("uptime_pct"), 2), MINT)])

        bar = self.tk.Frame(f, bg=BG)
        bar.pack(fill="x", padx=6, pady=(2, 6))
        self.tk.Label(bar, text="AI briefing", bg=BG, fg=MUTED,
                      font=MONO_B).pack(side="left")
        self._brief_btn = self._btn(bar, "Generate now", self._briefing_now, VIOLET)
        self._brief_btn.pack(side="right")

        txt = self.tk.Text(f, bg=SURFACE, fg="#d9c7ff", font=SANS, wrap="word",
                           relief="flat", height=10, insertbackground=INK)
        txt.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        # /api/briefing returns {"ok":True,"briefing":{"ts":..,"text":..}} — the
        # briefing is NESTED. Reading b["text"] (top level) was always None, so
        # the panel stayed on "No briefing yet" even after a successful generate.
        _br = (b or {}).get("briefing") or {}
        text = (_br.get("text") if isinstance(_br, dict) else None) \
            or "No briefing yet — press Generate now."
        txt.insert("1.0", text)
        txt.config(state="disabled")

        top = a.get("top_devices", [])
        if top:
            tv = self._table(f, ("device", "traffic"), (420, 200), height=7)
            for t in top:
                tv.insert("", "end", values=(t.get("name") or t.get("ip", ""),
                                             human_bytes(t.get("bytes", 0))))
        self.q.put(("status", "Analytics updated"))

    def _briefing_now(self):
        """Ask the server to generate a fresh AI briefing.

        The local AI can take a while, so this holds a sticky status for the
        duration and reports the outcome rather than silently finishing.
        """
        self._sticky("Asking the server's AI for a briefing \u2026 "
                     "(local models can take a minute)", 300)
        if hasattr(self, "_brief_btn"):
            try:
                self._brief_btn.config(state="disabled", text="Generating\u2026")
            except Exception:
                pass

        def work():
            r = self.api.post("/api/briefing_now", timeout=600)
            if r is None:
                out = "Briefing failed: " + (self.api.last_error or "no response")
            elif isinstance(r, dict) and r.get("error"):
                out = "Briefing failed: %s" % r["error"]
            else:
                out = "Briefing generated"
            self.q.put((lambda _: self._sticky(out, 12), None))
            self._hashes = getattr(self, "_hashes", {})
            self._hashes.pop("analytics", None)      # force the redraw
            self.q.put((lambda _: self.bg(self._load_analytics), None))
        self.bg(work)

    # ── Views & tools ─────────────────────────────────────────────────────
    # ── Flow map (Sankey) ──────────────────────────────────────────────────
    def _load_sankey(self):
        d = self.api.get("/api/topology3d")
        self.q.put((lambda _d: self._draw_sankey(_d), d))

    @staticmethod
    def _ribbon(x0, y0, x1, y1, w0, w1, steps=26):
        """Points for a flowing band from (x0,y0) to (x1,y1).

        Two cubic curves — the top edge out, the bottom edge back — so the
        polygon reads as a ribbon that thickens with traffic, the same shape
        the desktop and web views draw.
        """
        cx = (x1 - x0) * 0.5
        top, bot = [], []
        for i in range(steps + 1):
            t = i / steps
            mt = 1 - t
            bx = (mt ** 3) * x0 + 3 * (mt ** 2) * t * (x0 + cx) \
                + 3 * mt * (t ** 2) * (x1 - cx) + (t ** 3) * x1
            by = (mt ** 3) * y0 + 3 * (mt ** 2) * t * y0 \
                + 3 * mt * (t ** 2) * y1 + (t ** 3) * y1
            hw = (w0 * mt + w1 * t) * 0.5
            top.append((bx, by - hw))
            bot.append((bx, by + hw))
        pts = []
        for x, y in top:
            pts.extend([x, y])
        for x, y in reversed(bot):
            pts.extend([x, y])
        return pts

    @staticmethod
    def _mix(hex_colour, bg_hex, t):
        """Blend `hex_colour` toward `bg_hex` by t (0..1).

        Tk has no alpha channel. Stipple was the obvious substitute but it
        renders as a visible dot pattern, which reads as grain and dirt rather
        than glow. Mixing the actual RGB values gives a real gradient.
        """
        try:
            c = hex_colour.lstrip('#'); b = bg_hex.lstrip('#')
            cr, cg, cb = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            br, bg_, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
            t = max(0.0, min(1.0, t))
            return '#%02x%02x%02x' % (round(cr + (br - cr) * t),
                                      round(cg + (bg_ - cg) * t),
                                      round(cb + (bb - cb) * t))
        except Exception:
            return hex_colour

    @staticmethod
    def _fmt_bytes(b):
        b = float(b or 0)
        for u in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024 or u == "TB":
                return ("%.1f%s" % (b, u)) if (b < 10 and u != "B") else ("%d%s" % (b, u))
            b /= 1024.0
        return "%dB" % b

    def _draw_sankey(self, d):
        f = self.tabs["sankey"]
        self._clear(f)
        tk = self.tk

        if not d or not d.get("flows"):
            tk.Label(f, text="No active flows.\n\nStart an EtherApe capture on the "
                             "server, then this updates live.",
                     bg=BG, fg=MUTED, font=MONO, justify="left").pack(
                         anchor="w", padx=16, pady=16)
            return

        nodes = {n.get("id"): n for n in (d.get("nodes") or [])}
        flows = [x for x in d["flows"] if (x.get("bytes") or 0) > 0]
        flows.sort(key=lambda x: -(x.get("bytes") or 0))
        drawn = flows[:26]

        def is_local(ip):
            return bool((nodes.get(ip) or {}).get("local"))

        def name(ip):
            n = nodes.get(ip) or {}
            lbl = n.get("label") or n.get("rdns") or ip
            cc = n.get("cc") or ""
            flag = n.get("flag") or ""
            pre = (flag + " ") if flag else (("[%s] " % cc) if cc else "")
            return (pre + str(lbl))[:30]

        left, right, pairs = {}, {}, []
        for fl in drawn:
            src, dst = fl.get("src"), fl.get("dst")
            if not src or not dst:
                continue
            a, b = (src, dst) if is_local(src) or not is_local(dst) else (dst, src)
            left[a] = left.get(a, 0) + (fl.get("bytes") or 0)
            right[b] = right.get(b, 0) + (fl.get("bytes") or 0)
            pairs.append({"a": a, "b": b, "proto": fl.get("proto") or "other",
                          "bytes": fl.get("bytes") or 0, "pkts": fl.get("pkts") or 0,
                          "blocked": bool(fl.get("blocked")),
                          "attack": bool(fl.get("attack")), "raw": fl})
        if not pairs:
            tk.Label(f, text="No flows to draw yet.", bg=BG, fg=MUTED,
                     font=MONO).pack(anchor="w", padx=16, pady=16)
            return

        # ── layout: map on the left, host/flow tables and detail on the right,
        #    the same arrangement the desktop app uses ──────────────────────
        body = tk.Frame(f, bg=BG)
        body.pack(fill="both", expand=True)
        lft = tk.Frame(body, bg=BG)
        lft.pack(side="left", fill="both", expand=True)
        rgt = tk.Frame(body, bg=BG, width=430)
        rgt.pack(side="right", fill="y")
        rgt.pack_propagate(False)

        head = tk.Frame(lft, bg=BG)
        head.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(head, text="FLOW MAP", bg=BG, fg=CYAN, font=MONO_B).pack(side="left")

        def open_pihole():
            """Open the Pi-hole admin UI on the monitored machine."""
            import webbrowser
            from urllib.parse import urlparse
            host = urlparse(self.api.base).hostname or 'localhost'
            # Pi-hole is deployed alongside the server; the app maps its web UI
            # to 8081 by default.
            webbrowser.open('http://%s:8081/admin' % host)

        def open_web_sankey():
            """Open the server's full sankey view.

            The web page can do real gradients, glow and alpha, which a Tk
            canvas cannot - so the rich view lives there and this tab links to
            it rather than trying to imitate it badly.
            """
            import webbrowser
            webbrowser.open(self.api.base.rstrip('/') + '/sankey')

        tk.Button(head, text="\u2197 FULL VIEW", bg=RAISE, fg=CYAN,
                  activebackground=LINE, activeforeground="white", relief="flat",
                  font=("Consolas", 8, "bold"), cursor="hand2", padx=9, pady=2,
                  bd=0, highlightthickness=1, highlightbackground=CYAN,
                  command=open_web_sankey).pack(side="right", padx=(0, 6))

        tk.Button(head, text="\u25c9 PI-HOLE", bg=RAISE, fg=MINT,
                  activebackground=LINE, activeforeground="white", relief="flat",
                  font=("Consolas", 8, "bold"), cursor="hand2", padx=9, pady=2,
                  bd=0, highlightthickness=1, highlightbackground=MINT,
                  command=open_pihole).pack(side="right")
        tk.Label(head, text="  %d flows  \u00b7  %d internal  \u00b7  %d external"
                 % (len(pairs), len(left), len(right)),
                 bg=BG, fg=MUTED, font=MONO_S).pack(side="left")
        protos = []
        for pr in (p["proto"] for p in pairs):
            if pr not in protos:
                protos.append(pr)
        leg = tk.Frame(lft, bg=BG)
        leg.pack(fill="x", padx=12, pady=(0, 4))
        for pr in protos[:10]:
            c = tk.Frame(leg, bg=BG)
            c.pack(side="left", padx=(0, 12))
            tk.Label(c, text="\u25cf", bg=BG, fg=_proto_col(pr), font=MONO_S).pack(side="left")
            tk.Label(c, text=pr.upper(), bg=BG, fg=MUTED, font=MONO_S).pack(side="left", padx=(3, 0))

        cv = tk.Canvas(lft, bg=BG, highlightthickness=0)
        cv.pack(fill="both", expand=True, padx=12, pady=(2, 12))

        # ── right column: Active Hosts / Active Flows / Flow Detail ────────
        def panel(title, h):
            tk.Label(rgt, text=title, bg=BG, fg=CYAN,
                     font=("Consolas", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
            box = tk.Frame(rgt, bg=SURFACE, highlightthickness=1,
                           highlightbackground=LINE, height=h)
            box.pack(fill="x", padx=8)
            box.pack_propagate(False)
            return box

        hbox = panel("Active Hosts", 210)
        htv = self._table(hbox, ("ip", "name", "pkts", "bytes", "proto"),
                          widths=(120, 130, 45, 60, 55), height=9)
        fbox = panel("Active Flows", 190)
        ftv = self._table(fbox, ("source", "destination", "proto", "pkts", "bytes"),
                          widths=(115, 115, 50, 45, 60), height=8)

        # ── Analysis: the same BEHAV / TRAFFIC / IDS rules the desktop runs ──
        abar = tk.Frame(rgt, bg=BG)
        abar.pack(fill="x", padx=8, pady=(10, 2))
        tk.Label(abar, text="Analysis", bg=BG, fg=CYAN,
                 font=("Consolas", 9, "bold")).pack(side="left")
        abox = tk.Frame(rgt, bg=SURFACE, highlightthickness=1,
                        highlightbackground=LINE, height=150)
        abox.pack(fill="x", padx=8)
        abox.pack_propagate(False)
        atxt = tk.Text(abox, bg=SURFACE, fg=INK, font=("Consolas", 8), relief="flat",
                       wrap="word", padx=8, pady=6, highlightthickness=0)
        asb = tk.Scrollbar(abox, command=atxt.yview)
        atxt.configure(yscrollcommand=asb.set)
        asb.pack(side="right", fill="y"); atxt.pack(fill="both", expand=True)
        for tag, col in (("HIGH", RED), ("MED", AMBER), ("INFO", MUTED),
                         ("OK", MINT), ("sec", CYAN), ("body", INK)):
            atxt.tag_configure(tag, foreground=col)
        atxt.insert("1.0", "Pick an analysis above.", "INFO")
        atxt.configure(state="disabled")

        def run_analysis(kind, label):
            atxt.configure(state="normal"); atxt.delete("1.0", "end")
            atxt.insert("end", "Running %s analysis...\n" % label, "INFO")
            atxt.configure(state="disabled")
            def work():
                d = self.api.get("/api/analysis?kind=" + kind)
                self.q.put((lambda _d: show(_d, label), d))
            self.bg(work)

        def show(d, label):
            atxt.configure(state="normal"); atxt.delete("1.0", "end")
            if not d:
                atxt.insert("end", "No response from the server.", "HIGH")
                atxt.configure(state="disabled"); return
            head = "%s  \u00b7  %d hosts, %d flows%s\n\n" % (
                label, d.get("hosts", 0), d.get("flows", 0),
                "" if d.get("capturing") else "   (capture not running)")
            atxt.insert("end", head, "sec")
            for sec in (d.get("sections") or []):
                atxt.insert("end", "%s\n" % sec.get("section", ""), "sec")
                for it in (sec.get("items") or []):
                    sev = it.get("severity", "INFO")
                    atxt.insert("end", "  %-5s " % sev, sev if sev in
                                ("HIGH", "MED", "INFO", "OK") else "INFO")
                    atxt.insert("end", "%s\n" % it.get("host", ""), "body")
                    atxt.insert("end", "        %s\n" % it.get("detail", ""), "INFO")
                atxt.insert("end", "\n")
            atxt.configure(state="disabled")

        for _txt, _kind, _col in (("\u26a0 BEHAV", "behav", AMBER),
                                  ("\u25ce TRAFFIC", "traffic", VIOLET),
                                  ("\u2691 IDS", "ids", RED)):
            tk.Button(abar, text=_txt, bg=RAISE, fg=_col,
                      activebackground=LINE, activeforeground="white",
                      relief="flat", font=("Consolas", 8, "bold"), cursor="hand2",
                      padx=8, pady=2, bd=0, highlightthickness=1,
                      highlightbackground=_col,
                      command=(lambda k=_kind, l=_txt: run_analysis(k, l))
                      ).pack(side="left", padx=(8, 0))

        tk.Label(rgt, text="Flow Detail", bg=BG, fg=CYAN,
                 font=("Consolas", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
        dbox = tk.Frame(rgt, bg=SURFACE, highlightthickness=1, highlightbackground=LINE)
        dbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        detail = tk.Text(dbox, bg=SURFACE, fg=INK, font=MONO_S, relief="flat",
                         wrap="word", height=8, padx=10, pady=8,
                         insertbackground=INK, highlightthickness=0)
        detail.pack(fill="both", expand=True)
        detail.insert("1.0", "Click a flow above, or a ribbon on the map,\nto see details.")
        detail.configure(state="disabled")

        host_rows = sorted(nodes.values(), key=lambda n: -(n.get("bytes") or 0))[:60]
        for n in host_rows:
            htv.insert("", "end", values=(
                str(n.get("id", ""))[:22], str(n.get("label") or n.get("rdns") or "")[:20],
                n.get("pkts", 0), self._fmt_bytes(n.get("bytes")),
                str(n.get("proto") or "").upper()))

        flow_rows = sorted(flows, key=lambda x: -(x.get("bytes") or 0))[:80]
        for i, fl in enumerate(flow_rows):
            ftv.insert("", "end", iid=str(i), values=(
                str(fl.get("src", ""))[:20], str(fl.get("dst", ""))[:20],
                str(fl.get("proto") or "").upper(), fl.get("pkts", 0),
                self._fmt_bytes(fl.get("bytes"))))

        def show_detail(fl):
            n_s = nodes.get(fl.get("src")) or {}
            n_d = nodes.get(fl.get("dst")) or {}
            def who(ip, n):
                bits = [str(ip)]
                if n.get("label") and n["label"] != ip:
                    bits.append(str(n["label"]))
                loc = " / ".join(x for x in (n.get("city"), n.get("country")) if x)
                if loc:
                    bits.append(loc)
                if n.get("org"):
                    bits.append(str(n["org"]))
                return "\n    ".join(bits)
            flags = []
            if fl.get("blocked"):
                flags.append("BLOCKED by firewall")
            if fl.get("attack"):
                flags.append("SIMULATED HOSTILE (drill)")
            if n_d.get("suspicious") or n_s.get("suspicious"):
                flags.append("flagged suspicious")
            txt = (
                "SOURCE\n    %s\n\nDESTINATION\n    %s\n\n"
                "PROTOCOL   %s\nPACKETS    %s\nVOLUME     %s\n"
                % (who(fl.get("src"), n_s), who(fl.get("dst"), n_d),
                   str(fl.get("proto") or "?").upper(),
                   fl.get("pkts", 0), self._fmt_bytes(fl.get("bytes"))))
            if flags:
                txt += "\nSTATUS     " + "\n           ".join(flags) + "\n"
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            detail.insert("1.0", txt)
            detail.configure(state="disabled")

        def on_flow_select(_e=None):
            sel = ftv.selection()
            if not sel:
                return
            try:
                show_detail(flow_rows[int(sel[0])])
            except Exception:
                pass
        ftv.bind("<<TreeviewSelect>>", on_flow_select)

        lo = sorted(left.items(), key=lambda kv: -kv[1])
        ro = sorted(right.items(), key=lambda kv: -kv[1])
        maxb = max((p["bytes"] for p in pairs), default=1) or 1
        ribbons = {}

        def draw(_e=None):
            cv.delete("all")
            ribbons.clear()
            W = max(cv.winfo_width(), 400)
            H = max(cv.winfo_height(), 260)
            xL, xR = 150, W - 160
            if xR - xL < 120:
                return
            pad = 26
            def col_y(items):
                n = max(len(items), 1)
                step = (H - pad * 2) / n
                return {k: pad + step * (i + 0.5) for i, (k, _v) in enumerate(items)}
            yL, yR = col_y(lo), col_y(ro)
            cv.create_text(xL, 10, text="Internal Hosts", fill=MUTED, font=MONO_S, anchor="w")
            cv.create_text(xR, 10, text="External Servers", fill=MUTED, font=MONO_S, anchor="e")

            for pr in sorted(pairs, key=lambda p: p["bytes"]):
                a, b = pr["a"], pr["b"]
                if a not in yL or b not in yR:
                    continue
                wdt = 2 + (pr["bytes"] / maxb) * 22
                colour = RED if (pr["blocked"] or pr["attack"]) else _proto_col(pr["proto"])
                pts = self._ribbon(xL + 6, yL[a], xR - 6, yR[b], wdt, wdt)
                # Solid bands mixed toward the background: the wide body sits
                # back, the narrow core stays bright. No stipple - it speckles.
                item = cv.create_polygon(pts, fill=self._mix(colour, SURFACE, 0.62),
                                         outline="", smooth=True)
                mid_pts = self._ribbon(xL + 6, yL[a], xR - 6, yR[b],
                                       wdt * 0.55, wdt * 0.55)
                cv.create_polygon(mid_pts, fill=self._mix(colour, SURFACE, 0.28),
                                  outline="", smooth=True)
                core_pts = self._ribbon(xL + 6, yL[a], xR - 6, yR[b],
                                        max(1.4, wdt * 0.20), max(1.4, wdt * 0.20))
                core = cv.create_polygon(core_pts, fill=colour, outline="",
                                         smooth=True)
                ribbons[item] = pr
                ribbons[core] = pr

            for k, v in lo:
                y = yL[k]; r = 4 + min(6, (v / maxb) * 6)
                cv.create_oval(xL - r * 1.7, y - r * 1.7, xL + r * 1.7, y + r * 1.7,
                               fill=self._mix(CYAN, BG, 0.72), outline="")
                cv.create_oval(xL - r, y - r, xL + r, y + r, fill=CYAN,
                               outline=BG, width=2)
                cv.create_text(xL - 12, y, text=name(k), fill=INK, font=MONO_S, anchor="e")
            for k, v in ro:
                y = yR[k]; r = 4 + min(6, (v / maxb) * 6)
                nd = nodes.get(k) or {}
                oc = RED if nd.get("blocked") else (AMBER if nd.get("suspicious") else MINT)
                cv.create_oval(xR - r * 1.7, y - r * 1.7, xR + r * 1.7, y + r * 1.7,
                               fill=self._mix(oc, BG, 0.72), outline="")
                cv.create_oval(xR - r, y - r, xR + r, y + r, fill=oc,
                               outline=BG, width=2)
                cv.create_text(xR + 12, y, text=name(k), fill=INK, font=MONO_S, anchor="w")

        def on_canvas_click(ev):
            for item in reversed(cv.find_overlapping(ev.x - 2, ev.y - 2, ev.x + 2, ev.y + 2)):
                pr = ribbons.get(item)
                if pr:
                    show_detail(pr["raw"])
                    for iid in ftv.get_children():
                        vals = ftv.item(iid, "values")
                        if vals and vals[0] == str(pr["raw"].get("src", ""))[:20] \
                                and vals[1] == str(pr["raw"].get("dst", ""))[:20]:
                            ftv.selection_set(iid); ftv.see(iid)
                            break
                    return
        cv.bind("<Button-1>", on_canvas_click)
        cv.bind("<Configure>", draw)
        draw()

    # ── Remote agents ──────────────────────────────────────────────────────
    def _load_honeypot(self):
        d = self.api.get("/api/honeypot")
        self.q.put((lambda _d: self._draw_honeypot(_d), d))

    def _draw_honeypot(self, d):
        if self._unchanged("honeypot", d):
            return
        f = self.tabs["honeypot"]
        self._clear(f)
        tk = self.tk
        d = d or {}
        hits = d.get("hits") or []
        top = d.get("top") or []
        counts = {ip: n for ip, n in top}

        head = tk.Frame(f, bg=BG); head.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(head, text="\U0001f36f HONEYPOT", bg=BG, fg=MINT,
                 font=MONO_B).pack(side="left")
        _run = d.get("running")
        tk.Label(head, text="   %s  \u00b7  %d hits from %d source(s)"
                 % ("running" if _run else "stopped", d.get("total", 0),
                    d.get("unique_ips", 0)),
                 bg=BG, fg=MUTED, font=MONO_S).pack(side="left")

        note = tk.Frame(f, bg=SURFACE, highlightthickness=1, highlightbackground=LINE)
        note.pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(note, text="Decoy ports on the monitored machine. Every hit is a "
                            "scan or attack \u2014 there is no real service behind them. "
                            "Start and stop from the desktop app.",
                 bg=SURFACE, fg=MUTED, font=MONO_S, justify="left",
                 wraplength=1000).pack(anchor="w", padx=10, pady=6)

        # stat cards
        cards = tk.Frame(f, bg=BG); cards.pack(fill="x", padx=12, pady=(0, 8))
        for lbl, val, col in (("Connection Attempts", d.get("total", 0), RED),
                              ("Unique Sources", d.get("unique_ips", 0), AMBER),
                              ("Decoy Ports", len(d.get("ports") or []), CYAN),
                              ("Status", "RUNNING" if _run else "STOPPED",
                               MINT if _run else MUTED)):
            card = tk.Frame(cards, bg=SURFACE, highlightthickness=1,
                            highlightbackground=LINE)
            card.pack(side="left", expand=True, fill="both", padx=(0, 8))
            tk.Label(card, text=str(val), bg=SURFACE, fg=col,
                     font=("Consolas", 20, "bold")).pack(pady=(10, 0))
            tk.Label(card, text=lbl, bg=SURFACE, fg=MUTED,
                     font=MONO_S).pack(pady=(0, 10))

        if not hits:
            tk.Label(f, text="No hits recorded. On a clean network this is normal \u2014 "
                             "nobody has probed a decoy port.",
                     bg=BG, fg=MUTED, font=MONO, justify="left").pack(
                         anchor="w", padx=16, pady=16)
            return

        cols = ("time", "ip", "origin", "port", "service", "hits", "sample")
        heads = ("Time", "Source", "Origin", "Port", "Service", "Hits", "First bytes")
        widths = (72, 130, 80, 54, 96, 46, 300)
        tv = self.ttk.Treeview(f, columns=cols, show="headings", height=16)
        for c, h, w in zip(cols, heads, widths):
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        import time as _t
        for h in reversed(hits):
            tv.insert("", "end", values=(
                _t.strftime("%H:%M:%S", _t.localtime(h.get("time", 0))),
                h.get("ip", ""),
                "known LAN" if h.get("known") else "external",
                h.get("port", ""), h.get("service", ""),
                counts.get(h.get("ip"), 1), (h.get("sample") or "")[:60]))
        sb = tk.Scrollbar(f, command=tv.yview); tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); tv.pack(fill="both", expand=True,
                                                 padx=12, pady=(0, 12))

    def _load_firewall(self):
        d = self.api.get("/api/firewall")
        self.q.put((lambda _d: self._draw_firewall(_d), d))

    def _draw_firewall(self, d):
        if self._unchanged("firewall", d):
            return
        f = self.tabs["firewall"]
        self._clear(f)
        tk = self.tk
        d = d or {}
        blocked = d.get("blocked") or []

        head = tk.Frame(f, bg=BG); head.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(head, text="\u26d4 FIREWALL RULES", bg=BG, fg=AMBER,
                 font=MONO_B).pack(side="left")
        tk.Label(head, text="   %s  \u00b7  %d blocked  \u00b7  kill switch %s"
                 % (d.get("backend") or "no backend", d.get("count", 0),
                    "ON" if d.get("killswitch") else "off"),
                 bg=BG, fg=MUTED, font=MONO_S).pack(side="left")

        if not d.get("elevated"):
            warn = tk.Frame(f, bg="#2a1a0a", highlightthickness=1,
                            highlightbackground=AMBER)
            warn.pack(fill="x", padx=12, pady=(0, 8))
            tk.Label(warn, text="\u26a0  The monitored machine is not running "
                                "elevated \u2014 new blocks there will fail until it "
                                "is restarted as Administrator (or root).",
                     bg="#2a1a0a", fg=AMBER, font=MONO_S, justify="left",
                     wraplength=1000).pack(anchor="w", padx=10, pady=6)

        if not blocked:
            tk.Label(f, text="No hosts are currently blocked by the app.",
                     bg=BG, fg=MUTED, font=MONO, justify="left").pack(
                         anchor="w", padx=16, pady=16)
            return

        cols = ("ip", "rule", "state")
        tv = self.ttk.Treeview(f, columns=cols, show="headings", height=18)
        for c, h, w in (("ip", "Blocked address", 220),
                        ("rule", "Rule name", 320), ("state", "State", 120)):
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        for ip in blocked:
            tv.insert("", "end", values=(ip, "NM_BLOCK_%s" % str(ip).replace(".", "_"),
                                         "blocked"))
        for r in (d.get("rules") or []):
            if not str(r).startswith("NM_BLOCK_"):
                tv.insert("", "end", values=("\u2014", r, "active"))
        sb = tk.Scrollbar(f, command=tv.yview); tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); tv.pack(fill="both", expand=True,
                                                 padx=12, pady=(0, 12))

    def _load_agents(self):
        d = self.api.get("/api/agents")
        self.q.put((lambda _d: self._draw_agents(_d), d))

    def _draw_agents(self, d):
        f = self.tabs["agents"]
        self._clear(f)
        tk = self.tk
        agents = (d or {}).get("agents") or []
        if not agents:
            tk.Label(f, text="No remote agents configured.\n\n"
                             "Add them in the desktop app (Agents window); they will "
                             "appear here automatically.",
                     bg=BG, fg=MUTED, font=MONO, justify="left").pack(
                         anchor="w", padx=16, pady=16)
            return

        online = sum(1 for a in agents if a.get("online"))
        head = tk.Frame(f, bg=BG); head.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(head, text="REMOTE AGENTS", bg=BG, fg=CYAN, font=MONO_B).pack(side="left")
        tk.Label(head, text="   %d configured  \u00b7  %d online" % (len(agents), online),
                 bg=BG, fg=MUTED, font=MONO_S).pack(side="left")

        wrap = tk.Frame(f, bg=BG); wrap.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for i, a in enumerate(agents):
            ok = a.get("online")
            card = tk.Frame(wrap, bg=SURFACE, highlightthickness=1,
                            highlightbackground=MINT if ok else RED)
            card.pack(fill="x", pady=(0, 8))
            top = tk.Frame(card, bg=SURFACE); top.pack(fill="x", padx=10, pady=(7, 2))
            tk.Label(top, text="\u25cf", bg=SURFACE, fg=MINT if ok else RED,
                     font=MONO_S).pack(side="left")
            tk.Label(top, text=" " + str(a.get("label") or a.get("url") or "agent"),
                     bg=SURFACE, fg=INK, font=("Consolas", 10, "bold")).pack(side="left")
            sub = "%s  \u00b7  %s" % (a.get("hostname") or "?", a.get("ip") or a.get("url") or "")
            tk.Label(top, text="   " + sub, bg=SURFACE, fg=MUTED,
                     font=MONO_S).pack(side="left")
            if a.get("running_test"):
                tk.Label(top, text="   test running\u2026", bg=SURFACE, fg=AMBER,
                         font=MONO_S).pack(side="left")
            if not ok and a.get("error"):
                tk.Label(top, text="   " + str(a["error"])[:60], bg=SURFACE, fg=RED,
                         font=MONO_S).pack(side="left")

            row = tk.Frame(card, bg=SURFACE); row.pack(fill="x", padx=10, pady=(2, 8))
            def cell(parent, label, value, colour):
                c = tk.Frame(parent, bg=SURFACE); c.pack(side="left", padx=(0, 22))
                tk.Label(c, text=label, bg=SURFACE, fg=MUTED,
                         font=("Consolas", 7)).pack(anchor="w")
                tk.Label(c, text=value, bg=SURFACE, fg=colour,
                         font=("Consolas", 12, "bold")).pack(anchor="w")
            def num(v, unit="", dp=1):
                if v is None:
                    return "\u2014"
                try:
                    return ("%.*f%s" % (dp, float(v), unit))
                except Exception:
                    return str(v)
            cell(row, "DOWNLOAD", num(a.get("download"), " Mbps"), MINT)
            cell(row, "UPLOAD", num(a.get("upload"), " Mbps"), VIOLET)
            cell(row, "PING", num(a.get("ping"), " ms", 0), AMBER)
            cell(row, "DNS", num(a.get("dns"), " ms", 0), CYAN)
            for lbl, key, unit in (("CPU", "cpu_percent", "%"),
                                   ("MEM", "mem_percent", "%"),
                                   ("DISK", "disk_percent", "%"),
                                   ("TEMP", "temp_c", "\u00b0C")):
                if a.get(key) is not None:
                    v = float(a[key])
                    col = RED if v >= 90 else (AMBER if v >= 75 else MUTED)
                    cell(row, lbl, num(v, unit), col)

            hist = a.get("history") or []
            if len(hist) > 1:
                self._spark(card, hist, MINT, h=34)
            foot = tk.Frame(card, bg=SURFACE); foot.pack(fill="x", padx=10, pady=(0, 7))
            bits = []
            if a.get("last_test"):
                bits.append("last test " + str(a["last_test"])[:19].replace("T", " "))
            if a.get("samples"):
                bits.append("%d samples" % a["samples"])
            if a.get("interval_minutes"):
                bits.append("every %s min" % a["interval_minutes"])
            if a.get("version"):
                bits.append("agent " + str(a["version"]))
            tk.Label(foot, text="  \u00b7  ".join(bits), bg=SURFACE, fg=FAINT,
                     font=("Consolas", 7)).pack(anchor="w")

    def _load_views(self):
        self.q.put((lambda _: self._draw_views(), None))

    def _draw_views(self):
        if self._unchanged("views", self.api.base + str(self.api.caps)):
            return
        f = self.tabs["views"]
        self._clear(f)
        base = self.api.base

        self.tk.Label(f, text="Rich views open in your browser — they are WebGL "
                              "and HTML, and the server renders them directly.",
                      bg=BG, fg=MUTED, font=MONO_S, justify="left").pack(
                          anchor="w", padx=12, pady=(12, 8))

        grid = self.tk.Frame(f, bg=BG)
        grid.pack(fill="x", padx=8)
        views = [("3D topology", "/3d", CYAN),
                 ("Flow map (Sankey)", "/sankey", MINT),
                 ("Alerts & devices (web)", "/monitor", CYAN),
                 ("Analytics & AI", "/analytics", VIOLET),
                 ("VDI sessions", "/vdi", AMBER),
                 ("Full HTML report", "/api/report", INK),
                 ("User guide", "/guide", MUTED)]
        for i, (label, path, col) in enumerate(views):
            b = self.tk.Button(grid, text=label,
                               command=lambda p=path: webbrowser.open(base + p),
                               bg=SURFACE, fg=col, activebackground=RAISE,
                               activeforeground=INK, relief="flat", font=MONO,
                               cursor="hand2", anchor="w", padx=14, pady=10,
                               borderwidth=0, highlightthickness=1,
                               highlightbackground=LINE)
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=5, pady=4)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        self.tk.Label(f, text="ACTIONS", bg=BG, fg=FAINT,
                      font=("Consolas", 9, "bold")).pack(anchor="w",
                                                         padx=12, pady=(16, 4))
        act = self.tk.Frame(f, bg=BG)
        act.pack(fill="x", padx=8)
        for label, fn, col in [
                ("Run speed test", lambda: self._action("/api/run_test",
                                                        "Speed test started"), CYAN),
                ("Run DNS check", lambda: self._action("/api/run_dns",
                                                       "DNS check started"), MINT),
                ("Download CSV", lambda: self._download("/api/export?fmt=csv",
                                                        "network-history.csv"), INK),
                ("Download JSON", lambda: self._download("/api/export?fmt=json",
                                                         "network-history.json"), INK),
                ("ISP evidence PDF", lambda: self._download(
                    "/api/evidence?days=30", "isp-evidence-pack.pdf"), AMBER)]:
            self._btn(act, label, fn, col).pack(side="left", padx=4, pady=3)

        self.tk.Label(f, text="Server: %s" % base, bg=BG, fg=FAINT,
                      font=MONO_S).pack(anchor="w", padx=12, pady=(18, 2))
        caps = self.api.caps or {}
        self.tk.Label(f, text="API: %d GET endpoints, %d POST \u00b7 database: %s"
                             % (len(caps.get("api_get", [])),
                                len(caps.get("api_post", [])),
                                "yes" if caps.get("has_db") else "unknown"),
                      bg=BG, fg=FAINT, font=MONO_S).pack(anchor="w", padx=12)

    def _action(self, path, msg):
        def work():
            r = self.api.post(path, timeout=60)
            out = msg if r is not None else (
                "Failed: " + (self.api.last_error or "no response"))
            self.q.put((lambda _: self._sticky(out, 10), None))
        self.bg(work)
        self._sticky("Requesting \u2026", 60)

    def _download(self, path, filename):
        """Save a server-generated file locally.

        The dialog is parented to the main window (otherwise it can open
        *behind* it on Windows and look like nothing happened), and the result
        is shown as a sticky message so the 5s poll cannot wipe it.
        """
        from tkinter import filedialog, messagebox
        ext = os.path.splitext(filename)[1] or ""
        dest = filedialog.asksaveasfilename(
            parent=self.root, title="Save " + filename,
            initialfile=filename, defaultextension=ext,
            filetypes=[("This file", "*" + ext), ("All files", "*.*")])
        if not dest:
            self._sticky("Download cancelled", 4)
            return
        self._sticky("Downloading %s \u2026 (this can take a minute for the PDF)" % filename, 180)

        def work():
            try:
                data = self.api.get_raw(path, timeout=600)
                if not data:
                    raise ValueError("server returned an empty response")
                # A JSON error body means the server refused — don't save it
                # silently as if it were the file you asked for.
                if data[:1] == b"{" and b'"ok": false' in data[:200].lower():
                    raise ValueError(data[:200].decode("utf-8", "replace"))
                with open(dest, "wb") as fh:
                    fh.write(data)
                msg = "Saved %s (%s)" % (os.path.basename(dest), human_bytes(len(data)))
                self.q.put((lambda _: self._sticky(msg, 12), None))
                self.q.put((lambda _: self._offer_open(dest), None))
            except Exception as e:
                err = str(e)
                self.q.put((lambda _: self._sticky("Download failed: " + err, 20), None))
                self.q.put((lambda _: messagebox.showerror(
                    "Download failed",
                    "Could not download %s\n\n%s" % (filename, err),
                    parent=self.root), None))
        self.bg(work)

    def _offer_open(self, dest):
        from tkinter import messagebox
        try:
            if messagebox.askyesno("Saved",
                                   "Saved to:\n%s\n\nOpen it now?" % dest,
                                   parent=self.root):
                if sys.platform.startswith("win"):
                    os.startfile(dest)                     # noqa: S606
                else:
                    webbrowser.open("file://" + dest)
        except Exception:
            pass

    # -- lifecycle ----------------------------------------------------------
    def close(self):
        self._stop.set()
        try:
            self.root.destroy()
        except Exception:
            pass


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    server = None
    for i, a in enumerate(argv):
        if a in ("--server", "-s") and i + 1 < len(argv):
            server = argv[i + 1]
        elif a.startswith("--server="):
            server = a.split("=", 1)[1]
        elif a in ("--version", "-V"):
            print("%s %s" % (APP_NAME, VERSION))
            return 0
        elif a in ("--help", "-h"):
            print(__doc__)
            return 0
    try:
        import tkinter as tk
    except Exception:
        print("tkinter is required to run the client.")
        return 2
    root = tk.Tk()
    ClientApp(root, server)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
