# Changes this session — build `b-4d3f3e7a`

Thirty-four things this session. Build IDs for reference:

1. `b-346cdf46` — corrupt speed data purge (see note further down).
2. `b-86b6ab2d` — honeypot tarpit.
3. `b-dd991374` — attacker-seconds wasted, surfaced in the report + AI
   assessment.
4. `b-78978af4` — "Stuck now: 0" investigation + live "Held total" stat.
5. `b-48119510` — guide updated to cover all of the above.
6. `b-6446ed81` — Classic view removed entirely; guide rewritten to match.
7. `b-248b00b4` — firewall rules: search bar + host names, on every
   surface that lists them.
8. `b-d363c5f7` — merged the two `_NM_OUI` vendor tables into one.
9. `b-7b6beaf3` — 3D view: sparkle-flare starfield + glass walls.
10. `b-54bce347` — 3D view: traveling light pulses on the protocol bars
    (superseded by #11 below — you didn't like the look).
11. `b-2a88d56c` — 3D view: protocol bars redone as scrolling neon circuit
    traces.
12. `b-6cefa676` — 3D view: floor animated with glowing flow-path lines
    (superseded by #13 below — you wanted a packet-capture table instead).
13. `b-bdecb4b1` — 3D view: floor redone as a live scrolling packet-capture
    console (superseded by #14 below — you wanted it on the wall instead).
14. `b-a8335452` — 3D view: packet-capture console moved off the floor onto
    the left wall (superseded by #15 below — you wanted it lower).
15. `b-61579561` — 3D view: packet console lowered on the left wall.
16. `b-1fb06fce` — honeypot: higher tarpit capacity/hold time, five more
    decoy ports.
17. `b-ca2ce494` — 3D view: GRID toggle button.
18. `b-c954532e` — Wireshark Monitor: Clear now actually deletes the
    capture file instead of sometimes leaving it behind.
19. `b-d4a95b9d` — ISP Evidence Pack PDF: fixed a crash ("x and y must
    have same first dimension") when any download/upload/ping reading in
    the period was missing or implausible (this one, current).
20. (no build ID — this is the installer script, not the app) —
    `installer.nsi`/`build_installer.bat`: Npcap download URL was pinned
    to a stale version; bumped, plus a stale build-script banner fixed
    (this one, current).
21. (no build ID — build script only) — `build_installer.bat` now
    downloads and installs the NSIS inetc plugin automatically instead
    of requiring a manual download/extract/copy (could not be run
    end-to-end — no Windows box here, see caveat further down).
22. `b-4431b665` — installer now auto-installs a speed-test CLI
    (librespeed-cli) instead of requiring you to find one yourself; the
    app's own CLI-discovery code updated to match.
23. (no build ID — installer script only) — the auto-installed inetc
    plugin from #21 failed on your machine ("Plugin not found, cannot
    call inetc::get"); removed the inetc dependency from `installer.nsi`
    entirely instead of patching the plugin-installer further.
24. `b-b2a464b9` — added a Settings field for the advertised download/
    upload speed the ISP Evidence Pack compares against (previously
    config-file-only); also fixed the in-app guide's stale "five preset
    colour themes" line — it's actually twelve.
25. `b-b07a1ff4` — ISP Evidence Pack PDF is now dark-themed to match the
    rest of the app, using your active colour theme's download/upload/
    ping colours for the charts.
26. `b-8d732031` — Topology/EtherApe Sankey view: "[ BLOCKED ]" marker
    moved off the middle of the canvas onto the actual blocked external
    server it refers to.
27. `b-8834f5f5` — EtherApe window: new "LAN SCAN" button — active subnet
    scan with full name resolution, MAC/vendor, and open ports, shown as
    both a table and a live network map.
28. `b-738e198c` — LAN Scan map redone as an icon topology diagram (router
    hub + connected device icons with name/IP/ports underneath), replacing
    the plain dot-grid from #27.
29. `b-340c4b04` — LAN Scan is now several times faster: hosts are scanned
    concurrently instead of one at a time.
30. `b-a1d0e459` — LAN Scan map icons are now real device artwork, cropped
    from the Visio stencil screenshot you sent, instead of hand-drawn
    shapes.
31. `b-bfd27b6e` — main dashboard's "Live traffic" panel redone as a
    glowing hardware-monitor-style waveform, updating on its own faster
    timer.
32. `b-6e4d9e40` — top bar's duplicated Agents/Wireshark/Topology buttons
    removed; new "System" button opens a full System Monitor window built
    after watching Dave Plummer's Task Manager OG demo.
33. `b-9d6e28c2` — System Monitor rebuilt as a real multi-page app (Summary
    / Performance / Processes) after watching the actual video instead of
    working from a transcript alone.
34. `b-4d3f3e7a` — System Monitor: fixed silent GPU diagnostics + fixed the
    full-window rebuild on every page/tab click that was making it feel
    slow and clunky (this one, current).

## New: System Monitor rebuilt into three real pages after watching the video

**What you asked for:** "not a bad attempt however the video is now in
your built in browser. watch it to the 11 minute mark and add the
functionality" — i.e. the previous build (item 32) was a reasonable first
pass built from a transcript, but you wanted it actually checked against
the real thing and brought up to match.

**What I did:** used the browser to open the actual video and step
through it up to the 11-minute mark (via chapter markers and direct
timestamps, screenshotting the frames where the app's UI is on screen). A
transcript alone had missed that Task Manager OG isn't a single page — it
has its own left sidebar with real page navigation, and several things I'd
approximated turned out to have a specific, checkable design:

- **A left sidebar with real pages, not one long scrolling page.** Added
  SUMMARY / PERFORMANCE / PROCESSES to the System Monitor's own sidebar
  (separate from the main app's sidebar). Watching confirmed the real app
  has more pages than that (System Info, Startup Apps, Users, Services,
  Power & Freq, Benchmarks, Installed Apps, Disk Space) — see "Not done"
  below for why those specifically were left out.
- **Segmented LED-style bars.** Every tile and meter in the video has a
  small multi-segment bar underneath it, not just a number — added a
  `_draw_led_bar` helper (plain Canvas rectangles, no image assets) and
  wired it under all 4 top meters and all 7 Summary tiles.
- **GPU and NPU are separate tiles**, not combined — split them apart to
  match (7 tiles now instead of 6).
- **A Performance page** with its own left sub-nav (CPU / Memory / Network
  / Disks / GPU / Thermals) — confirmed the real app's flagship Performance
  view is a per-core CPU grid (one small graph per logical processor) plus
  a stats footer (utilization, speed, process/thread counts, uptime, core
  counts). Built that exact layout using `psutil.cpu_percent(percpu=True)`
  for the per-core numbers, with lightweight Canvas sparklines (not
  matplotlib) so redrawing 8-24 of them every cycle stays cheap. The other
  five sub-views (Memory/Network/Disks/GPU/Thermals) show one big glowing
  graph of that metric's own history, reusing the same glow-line technique
  as the Summary chart.
- **A real Processes page**, not just a mini top-N list — a searchable
  (`Filter:` box, matches name or PID), sortable (click any column header)
  table of every process, with a detail panel underneath showing whichever
  row is selected (Identity / Processor / Memory, mirroring the video's own
  three-column detail layout) and an "End process" button that actually
  terminates the selected process via `psutil.Process.terminate()` — gated
  behind a confirmation dialog first, the same way the video describes
  (Dave chose not to demo killing a process live, but named it as a real
  feature of his app; End Task is standard task-manager functionality, so
  it's wired up here, just never without you confirming first).
- The Summary mini process list and the full Processes-page table now
  share one process sample per refresh cycle (`_sample_processes`) instead
  of scanning `psutil.process_iter()` twice, so switching pages doesn't
  double the per-cycle cost.

**Verified (not assumed):**

- Headless functional test: constructed the window, confirmed the Summary
  page (10 chart lines, 14 mini-list rows, all 7 tile keys present, real
  CPU/clock numbers), then switched to Performance/CPU (correct core count
  for this sandbox, real "Processes"/"Threads"/"Up time"/core-count footer
  values), then Performance/Memory (a real single-metric graph line drew),
  then Processes (real row count matching the sandbox's actual process
  list), then typed "python" into the filter and got exactly 1 matching
  row back, then selected a row and confirmed the detail panel actually
  rendered (2 child widgets: the identity/processor/memory columns plus
  the End process button) — all through the real page-switching and
  filtering code paths, not by calling internals directly.
- Caught and fixed a real layout bug this way: the first pass at the 7-tile
  row only showed 3 tiles, because the LED-bar Canvas widgets had no
  explicit `width` and Tk's 200px default canvas width was starving later
  siblings out of the row entirely. Diagnosed by reading back each tile's
  actual `winfo_reqwidth()` (162/162/106/155/155/155/135 after the fix,
  all fitting the available ~1072px — before the fix, three tiles were
  reporting 412px each and the rest were reduced to 1px and invisible),
  not by guessing from how it looked.
- Rendered screenshots of all three pages plus a Performance/Network
  sub-view (sent alongside this changelog) — visual confirmation of the
  sidebar, the LED bars, the per-core grid, and the Processes table +
  detail panel all rendering correctly together with real sandbox data.
- Full `selftest.py`: 33/33 passed (Python 3.11, static + served-surface +
  JS checks; `/guide` route changed — rewrote the System button's guide
  section to describe the three pages — re-baselined, no other route
  changed) and 35/35 passed, 1 skipped (Python 3.12 under `xvfb-run`,
  desktop window + honeypot radar checks).

**Not done / your call:**

- I stopped adding pages at Summary/Performance/Processes. The video shows
  several more sidebar sections after Processes — System Info, Startup
  Apps, Users, Services, Power & Freq, Benchmarks, Installed Apps, Disk
  Space. Building all of those honestly (not just as inert nav buttons)
  would mean real OS-level enumeration for each — Windows service control
  manager queries, startup-registry reads, user account listings, and so
  on — which is a much bigger, more platform-specific project than what's
  built so far. Tell me which of those (if any) you actually want and I'll
  build that one next, rather than guessing at all of them.
- "End process" terminates via `psutil.terminate()` (a normal SIGTERM-style
  request), not a forced kill — a process that ignores it will keep
  running. That's the safer default; say if you want a forced/second-stage
  kill option too.
- The per-core Performance grid uses simple Canvas sparklines rather than
  matplotlib, specifically so redrawing many small graphs every cycle
  stays cheap — they're deliberately plainer (no glow) than the Summary
  chart, which is the one graph in this window worth spending the extra
  render cost on.

## New: System Monitor — GPU now tells you why it's N/A, and page/tab clicks are no longer a full window rebuild

**What you asked for:** "i installed python3 -m pip install nvidia-ml-py
but the gpu data still doesnt populate and the new features work well but
so slow and clunky" — two separate problems in the item-33 build: the GPU
tile staying N/A even after installing the package that's supposed to feed
it, and the new Summary/Performance/Processes window feeling sluggish to
click around in.

**What I did:**

- **GPU: stopped guessing, made the app tell you the real reason.**
  `_read_gpu_pct()` had two `except Exception: return None` blocks with no
  logging at all — every possible failure (pynvml not importable, NVML
  init failing, no GPU found, wrong Python environment, an old conflicting
  `pynvml` package) looked identical: a silent "N/A". It now catches the
  real exception, keeps it in `self._gpu_err`, and shows it right on the
  GPU tile and on the Performance→GPU graph instead of a bare "N/A" —
  logged via `_exc_debug` too. Most likely cause on your machine: you ran
  `python3 -m pip install nvidia-ml-py`, and this app is very likely
  launched by a *different* `python.exe` (a bundled venv from the
  installer, or a different interpreter on PATH) than whichever `python3`
  that pip command resolved to — the exact same class of bug we hit with
  `psutil` earlier this session. The tile will now spell that out directly
  (something like "pynvml import failed (ModuleNotFoundError: No module
  named 'pynvml') — likely installed into a different Python than the one
  running this app") instead of a dead-end "N/A", so you can tell at a
  glance whether it's an install-location problem, a missing/older
  NVIDIA driver, or something else — rather than me guessing which one
  applies to your setup.
- **Fixed the actual "slow and clunky" cause: page/tab switches were
  rebuilding the entire window from scratch.** `_switch_page()` and
  `_switch_perf_subview()` both called `_rebuild_ui()`, which destroys
  *every* widget under `self.root` — topbar (including the THEME
  dropdown, BLOOM checkbox, SATURATION slider), the sidebar, and the
  whole page — and rebuilds all of it from nothing, on every single click
  of SUMMARY / PERFORMANCE / PROCESSES or a Performance sub-tab. Now
  `_switch_page()` only destroys and rebuilds the content area
  (`_show_page()`) and patches the sidebar button colours in place, and
  `_switch_perf_subview()` only rebuilds the Performance page's own
  content — the topbar and its controls are never touched by a page
  click at all. Theme changes still do a full rebuild (recolouring every
  widget genuinely does need to touch everything), so that one control
  is unchanged.
- **Stopped scanning every process every 500ms regardless of which page
  is showing.** `_sample_processes()` did a full `psutil.process_iter()`
  walk (name, status, username, memory, thread count, per-process CPU%)
  every refresh cycle no matter what was on screen — even on
  Performance→Network, which never displays a single process row. It now
  only runs the full scan on Summary and Processes (the two pages that
  actually show per-process detail); Performance→CPU gets a cheap `light`
  scan (just PID + thread count, for the footer's process/thread totals);
  every other Performance sub-view (Memory/Network/Disks/GPU/Thermals)
  skips process sampling entirely.

**Verified (not assumed):**

- Headless test: captured the Tk widget id of the topbar frame and all
  three sidebar buttons, then drove the window through
  `_switch_page('performance')` → `_switch_perf_subview('net')` →
  `_switch_page('processes')` → `_switch_page('summary')` — the topbar's
  widget id and every sidebar button's widget id were identical before
  and after all four switches, confirming the topbar/sidebar are no
  longer destroyed and recreated on page clicks (a full rebuild would
  have produced new widget ids each time).
- Timed the old vs. new page-switch path directly (`_rebuild_ui()` vs.
  the new `_switch_page()`), 9 switches each, in this sandbox: old full
  rebuild averaged **53.8ms/switch**, new content-only switch averaged
  **35.4ms/switch** — roughly a third faster here, and that gap should be
  larger on a real Windows machine, since the old path also had to
  reconstruct the topbar's `OptionMenu`/`Scale`/`Checkbutton` widgets and
  re-run `ttk.Style` setup each time, which this sandbox's minimal Tk
  build does cheaply but a real desktop environment typically doesn't.
  Fewer widgets being torn down and recreated also means less flicker,
  which matters for how "clunky" a switch feels even beyond raw ms.
- Timed `_refresh_once()` (the 500ms-cycle work) per page in this sandbox
  (64 processes; a Windows desktop typically has 200–400, so the process-
  scan savings below should scale up further there): Summary ~33.7ms,
  Processes ~11.1ms, Performance→CPU (light scan) ~3.8ms, Performance→
  Network (no scan at all — cost is only the graph redraw) ~12.6ms.
- Forced `import pynvml` to fail with `ModuleNotFoundError` in a test and
  confirmed `_read_gpu_pct()` returns `None` with `self._gpu_err` set to
  the real message described above, instead of a bare unexplained "N/A".
- Confirmed the light vs. full process-scan split actually returns
  different data: full scan rows have real process names; light-scan rows
  come back with blank names (as designed — Performance→CPU never
  displays them, only counts them).
- Full `selftest.py`: 33/33 passed (Python 3.11 — `/guide` text untouched
  this round, no re-baseline needed) and 35/35 passed, 1 skipped (Python
  3.12 under `xvfb-run`).

**Not done / your call:**

- I couldn't reproduce your exact pynvml failure here (this sandbox has no
  NVIDIA GPU at all), so I can't tell you the precise message you'll see —
  only that the app will now show you the real one instead of a bare
  "N/A". If it still says "pynvml import failed" after this update, run
  `python -c "import sys; print(sys.executable)"` using the exact same
  Python you use to launch/build this app (not just any `python3` in a
  terminal), then `pip install nvidia-ml-py` with *that* interpreter. If
  it instead shows an NVML error (not an import error), that points to a
  driver/hardware issue rather than a packaging one — paste me the exact
  message and I'll dig into that specific error.
- Theme switching (the THEME dropdown) still does a full window rebuild —
  left alone on purpose, since recolouring every themed widget genuinely
  does need to touch the whole tree, and it's an infrequent action, not
  something you'd click repeatedly.
- Didn't change the fixed 500ms refresh interval itself — no evidence
  pointed at that as the cause of "clunky," and I didn't want to change
  something un-asked-for on a guess.

## New: "System" button — a Task-Manager-OG-inspired System Monitor window

**What you asked for:** "in the main page remove the duplicated agents
wireshark and topology buttons at the top. create a system button. then
watch this video untill the 11 minute mark [Shop Talk #91, Dave Plummer]
... create everything shown in the video all working that launches when
the button is clicked."

**Removing the duplicated top-bar buttons:** the top bar's Agents /
Wireshark / Topology shortcuts opened the exact same three windows as the
sidebar's WS CAPTURE / TOPOLOGY / AGENTS buttons — genuinely duplicated,
not just similarly named. Removed all three from the top bar; they're
still one click away on the sidebar, nothing lost. The top bar now shows
just Dashboard and the new System button.

**What's in the video (first 11 minutes), and what I could actually
verify about it:** the video is "Windows Task Manager's Creator Rebuilt
It 30 Years Later | Shop Talk #91" (Dave's Attic). I can't literally watch
video — I pulled the title via YouTube's oembed endpoint, then a
transcript for 0:00-11:00, plus a couple of tech-press writeups (Windows
Central, Tom's Hardware) covering the same tool for corroboration. Dave
Plummer — who wrote the original 1994 Windows NT Task Manager — demos a
from-scratch rebuild he calls "Task Manager OG": a live CPU graph with
green = usage and red = kernel time, a GPU/temperature section, a
top-processes list where "rows that change get a green background," tiles
for memory/disk/network/energy/GPU/NPU/thermal, and a customization panel
with a saturation slider that "goes to 11" (default 7), an independent
bloom on/off toggle, and colour-scheme presets (mono, green phosphor,
amber, blue, plus light mode).

**What I built:** his app is closed-source and not (yet) available for
Windows, so this isn't a copy of his code — it's a working recreation of
the features actually described, wired to this app's own live telemetry
via `psutil`:

- A new `SystemMonitorWindow`, opened by the System button: a glowing CPU
  (green-ish) / kernel-time (red-ish) line chart with a soft neon-glow
  render (same layered-alpha technique as the Live Traffic panel above),
  a temperature line on a second axis when a sensor is available, and a
  triangle marker on the current value at the right edge, same as the
  video's readout style.
- A top-processes list (`psutil.process_iter`, sorted by CPU%, refreshed
  every cycle) where a row flashes the theme's accent colour when that
  process's CPU% just moved by 3+ points, and gets a distinct colour the
  first time a process appears in the list — "rows that change get a
  green background" and "processes as they come in and leave," as
  described.
- Six tiles: Memory, Disk (with read/write MB/s), Network (RX/TX Mbps),
  Energy/Battery, GPU/NPU, and Thermal.
- The customization panel described: a THEME picker with six presets
  (Neon — this app's own default, plus Mono, Green Phosphor, Amber, Blue,
  and Light, covering every scheme the video names), an independent BLOOM
  checkbox, and a SATURATION slider running 0-11 with a default of 7 —
  same range and default the video calls out. Saturation scales how many
  extra glow layers get drawn; bloom is a separate all-or-nothing switch
  for whether there's any glow at all, matching the video's "these are two
  separate controls" framing.
- CPU%, CPU clock speed, memory, disk usage/IO, network, and battery are
  all real readings from this machine via `psutil` — not placeholders.

**Verified (not assumed):**

- Headless functional test: constructed the window under `xvfb-run`,
  confirmed the chart actually draws lines (10 canvas lines with bloom on
  and default saturation — 4 glow layers + 1 crisp line, × 2 series), that
  switching every one of the 6 themes doesn't throw, and that toggling
  saturation to 0 collapses the chart to 4 flat lines (no glow) while
  saturation 11 with bloom back on produces 14 lines (more glow layers) —
  proving the sliders actually change what's drawn, not just cosmetic
  labels.
- Same test confirmed real, moving numbers: CPU%, CPU clock (2.80 GHz),
  memory (10-11%, real used/total bytes), disk usage and I/O rate, and
  network RX/TX all populated with this sandbox's actual values across
  three timed snapshots — not hardcoded strings.
- Rendered a full screenshot of the window (sent alongside this
  changelog) — visual confirmation of the glowing chart, the coloured "●
  CPU / ● Kernel" readout, the top-processes list (with a process that had
  just appeared correctly flashed green), and all six tiles rendering
  their real values within their card bounds — this took two passes: the
  first screenshot showed the tile row nearly invisible because the
  chart's expand="True" area was squeezing it toward zero height, which I
  fixed with the same fixed-height-frame technique this file already uses
  for its top bar and view bar, then re-verified.
- Confirmed via a separate headless test that clicking the actual "System"
  button in the real top bar (not just constructing the class directly)
  opens the window without raising an exception, and that the top bar's
  button list is now exactly `['Dashboard', 'System']`.
- Full `selftest.py`: 33/33 passed (Python 3.11, static + served-surface +
  JS checks; `/guide` route changed — updated the Top Bar section and
  added a System button section — re-baselined, no other route changed)
  and 35/35 passed, 1 skipped (Python 3.12 under `xvfb-run`, desktop
  window + honeypot radar checks).

**Not done / your call:**

- This is an honest recreation of what the video describes, not a
  pixel-exact clone — I don't have Dave Plummer's actual app to copy, only
  a transcript and press coverage. If you've since tried the real Task
  Manager OG yourself and want something specific matched more closely
  (exact colours, exact layout, specific meter styles), tell me what to
  change and I will.
- CPU temperature: `psutil.sensors_temperatures()` isn't implemented on
  Windows at all (it's a Linux/macOS-only psutil feature) — on your
  Windows machine this will always show "N/A on this platform," same as
  it does in the sandbox screenshot I'm sending (this sandbox has no
  thermal sensors exposed either, so both platforms hit the honest
  fallback, just for different reasons). If you want real CPU temps on
  Windows, that needs a separate library (e.g. `OpenHardwareMonitor`/
  `LibreHardwareMonitor` via WMI, or `wmi` + a vendor-specific sensor
  driver) — not something I added, since it's a real extra dependency and
  install step, not a one-line addition.
- GPU utilization only works with an NVIDIA GPU and the optional `pynvml`
  package installed; without both it honestly shows "N/A (needs NVIDIA +
  pynvml)" rather than a fake number. AMD/Intel GPU stats aren't wired up
  at all — there's no single cross-vendor Python library for that.
- NPU always shows "N/A (no OS API yet)" — there's no standard way to read
  NPU utilization from Python on any OS today, so I didn't fake one.
- The refresh cycle runs every 500ms in this build (visible in the "cycle
  __ms" readout in the window's top-right), not the 60Hz the video
  mentions — a Tkinter+matplotlib canvas redraw doing this much per frame
  can't honestly hit 60Hz, so I picked a rate that's still clearly "live"
  (twice the Live Traffic panel's own 400ms) without claiming a number I
  can't back up. The on-screen "cycle Xms" label reports the real measured
  time each refresh actually takes, so you can see for yourself rather
  than take my word for it.

## New: Live traffic panel now looks and updates like a hardware monitor

**What you asked for:** "I WANT THE LIVE TRAFFIC VIEW on the main page to
look like the attached and update in real time" — with a ~10-second video
showing an MSI-Afterburner-style scrolling multi-line graph: dark
background, bright glowing lines, a bright frame border, grid lines, and
small triangle markers at the right edge showing each line's current
value.

**What I did:** This is the bottom-left panel of the six-panel chart grid
on the main dashboard — the one that plots actual TX/RX network throughput
sampled from your machine via psutil (not your recorded speed-test
history). I gave it its own draw method (`_update_live_traffic`) instead
of folding it into the shared chart-refresh code, so it can be styled and
updated differently from the five panels around it:

- Bright green (`#39ff14` — the same "this is live" green already used
  elsewhere in the app, e.g. the SCAN button and the 3D view's GRID
  toggle) frame border and grid lines on a dark panel, instead of the
  plain thin border the other panels use.
- Each line (RX and TX) is drawn as a soft glow: several progressively
  wider, fainter copies of the same line behind one crisp top line. This
  is a plain matplotlib technique (`_glow_line`, layered `ax.plot()` calls
  at low alpha) — no image filters or extra libraries needed, so it works
  the same on your machine as it did in my test.
- A colour-coded "● RX 12.3 / ● TX 4.1 / Mbps" readout across the top of
  the panel, in your existing Download/Upload theme colours, in place of
  the plain grey title text.
- A small white triangle marker pinned to each line at the right edge,
  sitting right on the current value — the "live readout" look from your
  video.
- The panel now refreshes on its own independent 400ms timer
  (`_refresh_live_fast`), instead of only redrawing whenever the rest of
  the dashboard does its full refresh every 2 seconds. That's what makes
  it visibly animate in real time rather than jumping every couple of
  seconds along with everything else.
- Updated the in-app Guide's "Live network traffic (bottom-left)" entry to
  describe the new look and the faster independent refresh.

**Verified (not assumed):**

- Headless functional test (`ModernWindow` constructed under `xvfb-run`,
  with the real refresh timers running, snapshotted twice 1.5 seconds
  apart): confirmed 10 canvas line objects on the panel each time (4 glow
  layers + 1 crisp line, × 2 series for RX/TX), the frame's border colour
  reading back as `#39ff14` at the intended alpha, and the "● RX", "● TX",
  "Mbps" text labels present. Between the two snapshots, the panel's
  internal sample history grew (2–3 samples → 7–8 samples) — direct proof
  the independent 400ms timer is actually running and pulling new psutil
  readings on its own, not just sitting static between the main 2-second
  refreshes.
- Rendered a full screenshot of the live dashboard from that same test run
  (sent alongside this changelog) — visual confirmation the frame, glow
  lines, colour-coded readout, and triangle markers all render together
  correctly on the actual chart grid, not just in isolation.
- Full `selftest.py`: 33/33 passed (Python 3.11, static + served-surface +
  JS checks; `/guide` route changed because of the updated Live Traffic
  wording — re-baselined, no other route changed) and 35/35 passed, 1
  skipped (Python 3.12 under `xvfb-run`, desktop window + honeypot radar
  checks).

**Not done / your call:**

- The panel's two lines use your existing Download/Upload theme colours
  (whatever you've picked in Settings), not the literal green/orange/red
  scheme from the reference video — the video's colours mark three
  different metrics (utilization, temperature, kernel load) that don't
  have an equivalent here; RX/TX already have established colours
  elsewhere in this app, so I kept those for consistency rather than
  introducing a second, conflicting colour scheme just for this one panel.
- The screenshot I'm sending shows RX/TX reading near zero — that's a
  real reflection of this sandboxed test machine's quiet network during
  the capture, not a bug in the panel. On your machine, with real network
  traffic, the lines and the "● RX / ● TX" numbers will move accordingly.

## New: LAN Scan map icons are now real artwork, not hand-drawn shapes

**What you asked for:** "use these icons" — the two `.vss` Visio stencil
files you sent, after telling me you didn't like the plain hand-drawn
icon shapes from the previous build.

**What actually happened with the `.vss` files themselves:** I could not
get usable images out of them, for a real technical reason, not a
"didn't try hard enough" one — see the previous changelog entry's "Not
done" note for the three approaches I tried (LibreOffice conversion, its
scripting API, raw binary inspection) and why the old binary `.vss`
format doesn't give up its images that way. What I could do instead: you
had already sent a screenshot earlier in this conversation showing that
same "Network and Peripherals" stencil rendered in Visio, with clean,
readable icons and labels. That's a rendered image, not a proprietary
binary format — I can work with that directly.

**What I did:**

- Measured the screenshot's grid pixel-by-pixel (not guessed) to find
  the exact boundaries of six icons: Router, Server, Mainframe, Printer,
  Hub, and Wireless Router.
- Cropped each one out, then removed its background (the pale blue
  stencil-cell backdrop) so it sits cleanly on the app's dark canvas
  instead of looking like a pasted sticker — this took a few passes to
  get right, since a simple "replace this exact colour" approach either
  left a halo around each icon or ate into the icon's own light-coloured
  parts (the icons are soft-shaded product photos, not flat clip art, so
  there's no clean single "background colour" to key out). Settled on a
  flood-fill from the corners inward, which only clears background that's
  actually connected to the edge, not just any similarly-coloured pixel
  anywhere in the icon.
- Embedded the six results as small base64-encoded PNGs directly in the
  script (~2.5KB each, ~18KB total) — the app stays one file, no new
  external assets to ship or lose track of.
- Wired them into the map: Router → the router/gateway hub, Server tower
  → "This PC" and "Windows PC" guesses, Mainframe → "Server/SSH" guesses,
  Printer → printer guesses, Hub → "NAS/Storage" guesses, Wireless Router
  → "IoT/Smart device" guesses. The one guessed type with no honest match
  in that stencil — "Device (unidentified)" — keeps the hand-drawn "?"
  circle instead of being forced into a real-looking icon that would
  overstate how sure the guess is.

**Verified (not assumed):**

- Confirmed via `tk.PhotoImage` directly (not just "the file exists") that
  all six embedded icons decode correctly under Tk's native PNG support —
  same mechanism Windows Tk will use, no PIL or other runtime image
  library required.
- Headless UI test with 7 synthetic hosts covering every guessed type
  (router, Windows PC, server, printer, NAS, IoT, and one unidentified
  device with no open ports): counted the actual canvas image items
  created (7 — six real-icon nodes plus the "This PC" node, which also
  gets a real icon; the unidentified host correctly falls back to the
  hand-drawn "?" and is not counted as an image item) — confirmed
  programmatically, not eyeballed.
- Rendered screenshot of that same 7-host test (sent alongside this
  changelog) — visual confirmation the icons, labels, connecting lines,
  and orange open-port badges all render together correctly, and that the
  background removal looks clean at the actual on-map size, not just in
  an isolated crop.
- Full `selftest.py`: 33/33 passed (Python 3.11, static + served-surface +
  JS checks; `/guide` route changed because of the updated LAN Scan
  wording — re-baselined, no other route changed) and 35/35 passed, 1
  skipped (Python 3.12 under `xvfb-run`, desktop window + honeypot radar
  checks).

**Not done / your call:**

- Background removal isn't pixel-perfect at extreme zoom — the Mainframe
  icon in particular keeps a faint light edge on two sides (visible if
  you zoom in a lot; not really visible at the map's normal icon size).
  I tried a more aggressive pass to fully clean it but that started
  eating into the icon artwork itself on a couple of the icons, which is
  a worse trade, so I kept the milder pass.
- Only six icons were pulled from your screenshot — enough to cover every
  guessed device type this feature currently has. If you want more
  specific types later (say, a distinct camera or smart-speaker icon
  instead of the generic "IoT/Smart device" one), I'd need either a
  clearer source image for that specific icon or you exporting it
  yourself.

## New: LAN Scan runs several hosts at once instead of one at a time

**What you asked for:** "make the scan much quicker."

**Where the time was actually going:** the previous build scanned hosts
strictly one after another — for each host, port-scan it (up to ~1,140
ports), *then* resolve its hostname, *then* move to the next host. A
host that doesn't answer probes (the common case for a Windows PC with
its default firewall on, which silently drops unsolicited connections
instead of rejecting them) pays close to the full per-port timeout on
every one of those ~1,140 ports. Multiply that by every host on your
subnet, one at a time, and a normal home network's total scan time adds
up fast — this was the real bottleneck, not the port count or the
per-port timeout themselves.

**The fix — measured, not guessed at:**

- Hosts now scan **concurrently**: up to 6 hosts are port-scanned and
  name-resolved at the same time instead of strictly one after another.
  A shared budget of ~720 port-scanning threads is split across however
  many hosts are active at once, rather than just multiplying per-host
  concurrency by the number of hosts unboundedly.
- Per host, the port scan and the name resolution — previously back to
  back — now also run concurrently with each other, since neither
  depends on the other's result.
- The discovery ping sweep (the phase before port scanning even starts)
  went from 64 to 160 concurrent pings, which covers a full /24 in 2
  rounds of the ping timeout instead of 4 — same number of real pings
  sent, just more of them in flight at once, so no host is skipped or
  scanned less thoroughly.
- The per-port connect timeout dropped slightly, from 0.5s to 0.4s — LAN
  round-trip times are normally sub-millisecond, so this still leaves
  roughly 400x headroom for a live host to respond; it only shortens the
  worst case (a port that never answers at all).
- Port count and scan scope are unchanged — still the full ~1,140-port
  "thorough" scan you asked for when I first built this, just run with
  the hosts overlapped instead of serialized. Nothing was cut to make
  this faster.

**Verified (not assumed):**

- Because this sandbox has no real LAN with firewalled hosts to reproduce
  the worst case against, I verified the *mechanism* directly instead of
  eyeballing a wall-clock number: a test with 12 synthetic hosts, each
  taking a fixed simulated 0.5s to "scan," recorded exactly how many
  hosts were mid-scan at the same moment — the measurement showed 6
  hosts genuinely overlapping in time (matching the intended cap), not
  just queued back to back. The whole batch finished in ~1.1s versus the
  6.0s a strictly-sequential version of the same test would have taken —
  a ~5.5x speedup in this scenario, and the honest reason is real
  concurrency, confirmed by the overlap count, not just a faster clock.
- Real-socket port detection re-checked at the new settings (0.4s
  timeout, the same variable worker count the scan window now computes):
  3 real local listeners plus 3 known-closed ports, found exactly the 3
  open ones — same correctness as before, at the tighter timeout.
- Full `selftest.py`: 33/33 passed (Python 3.11, static + served-surface
  + JS checks — no route content changed, so no re-baseline needed) and
  35/35 passed, 1 skipped (Python 3.12 under `xvfb-run`, desktop window +
  honeypot radar checks).

**Not done / your call — the icon request:**

You also asked me to use the two Visio stencil files you sent
(`Icons.vss`, `2D Icons.vss`) for the map's device icons. I looked into
it properly before giving up on it: tried opening them with LibreOffice
headlessly (produces a blank page — stencil masters aren't placed on a
canvas, so a plain document conversion doesn't surface them), tried
driving LibreOffice's scripting interface to pull the masters out
directly (couldn't get a stable connection to it in this sandbox), and
inspected the raw file structure with a binary OLE-file reader looking
for embedded picture data (found no extractable image data — these are
the older, pre-2013 binary `.vss` stencil format, which packs every
shape into one large proprietary binary blob rather than the ZIP-of-XML-
and-images structure the modern `.vssx` format uses; there's no
practical way to pull clean icons back out of that format without Visio
itself). I did not fabricate icons and pass them off as "from your
stencil" — I'd rather tell you it didn't work. This is a separate,
still-open item from the scan-speed fix in this entry; I'm asking you
how you'd like to proceed with it separately.

## New: LAN Scan map redrawn as an icon topology diagram

**What you reported:** the LAN Scan map from the previous build (a 16×16
grid of plain coloured dots, one per possible address) wasn't what you
wanted at all. You wanted something closer to the icon-based network
diagrams from tools like the Visio "Network and Peripherals" stencil you
showed me — recognisable device icons, IP/name/ports printed under each
one, and the connections between devices actually drawn.

**What changed:** the map is now a labelled icon topology instead of a
grid of dots.

- **Icons, not dots.** Each discovered host gets a small flat icon drawn
  to match a guessed device type: router, this PC, Windows PC, server,
  printer, NAS/storage, IoT/smart device, or a plain "?" circle when
  nothing points to any of those. A small orange badge on the icon's
  corner marks a host with at least one open port.
- **Labels under every icon.** Directly below each icon: its device-type
  guess (top caption), then hostname (or IP if unresolved), then IP
  address, then its open ports (or "no open ports").
- **Connections drawn.** The map is a star: your default gateway (read
  from the OS routing table, same source the app already used elsewhere)
  sits in the middle, and every other discovered host — including this
  PC itself, shown as a distinct node — is drawn with a line straight to
  it. Clicking a host highlights its line.
- **Device type is clearly marked as a guess.** Every icon's caption ends
  in "(guessed)" except the router and this-PC nodes, which are known for
  certain (from the OS routing table and the socket the scan itself runs
  from, not inferred). The type guess itself comes only from open ports,
  MAC vendor string, and hostname — nothing queries a device about what
  it actually is.
- **Map is now the main view.** It moved to the top of the window as a
  large, scrollable canvas; the sortable table and the selected-host
  detail panel moved into a shorter strip along the bottom, still fully
  functional (sort, click-to-select, live streaming as hosts are found).

**Why a star centred on the router, not a real device-to-device diagram:**
this app has no way to see which physical switch port each device is
plugged into — that needs SNMP or LLDP access to a managed switch, which
almost no home router or unmanaged switch exposes. What it does know for
certain is which hosts answered ARP/ping on your subnet and which one is
the default gateway. "Every device reaches the rest of the network through
the router" is the accurate way to draw that with the data actually
available, so that's what this draws — it is not a guess dressed up as a
real topology.

**Verified (not assumed):**

- Headless UI test under `xvfb-run`, 5 synthetic hosts including the
  gateway itself among the discovered hosts (the realistic case, since a
  router almost always answers ARP on its own subnet): confirmed the
  gateway host is drawn as the hub, all 5 hosts plus a synthetic "this PC"
  node all get distinct canvas nodes (6 total, counted programmatically —
  not eyeballed), clicking a host and clicking the "this PC" node both
  update the detail panel correctly, and the table still sorts and stays
  in sync with the map.
- Device-type guess function checked directly against known inputs:
  ports `[3389, 445]` → Windows PC, `[9100]` → printer, no ports → generic
  device, `[22, 80]` → server — all confirmed programmatically.
- Stress-tested with 22 synthetic hosts (not just the small 4-5 host case)
  to check the layout scales without crashing or throwing: all 22 hosts
  plus the self node rendered as distinct nodes with no exceptions, and
  the canvas's scroll region grew to fit rather than clipping content —
  checked via a rendered screenshot, not just absence-of-exception.
- Rendered screenshots of both the 5-host and 22-host cases (5-host one
  sent alongside this changelog) — confirms visually that icons, labels,
  and connecting lines are legible and don't overlap badly even with a
  couple dozen hosts.
- Full `selftest.py`: 33/33 passed (Python 3.11, static + served-surface +
  JS checks; the `/guide` route content changed because of the updated
  LAN Scan section — re-baselined and confirmed no other route changed)
  and 35/35 passed, 1 skipped (Python 3.12 under `xvfb-run`, includes the
  desktop window and honeypot radar checks).

**Not done / your call:**

- Real device-to-device switch topology (which port on which switch each
  device is plugged into) isn't something this app can discover without
  SNMP/LLDP access to a managed switch — see the star-topology rationale
  above. If you have a managed switch and want that level of detail, it'd
  need new SNMP-polling code and your switch's credentials; tell me if
  that's worth building.
- The device-type icon is still a guess from ports/vendor/hostname, same
  caveat as before — it can be wrong, especially for anything that
  doesn't expose a recognisable open port (most phones and tablets show
  up as a generic "?" device).
- With a lot of hosts (a busy /24 could have 100+), the star can get
  crowded even with scrolling; I haven't built a zoom control or a
  cluster/collapse view for very large networks — say if that's something
  your actual network needs.

## New: "LAN SCAN" button in the EtherApe/Topology window — live network map with name resolution, MAC/vendor, and open ports

**What you asked for:** "in the etherape window i want a map button which
will create a live network map of my network with full name resolution
ip adress and open ports."

**Why this is new territory:** every other feature in this window (and in
the app generally) is passive — it only ever describes traffic it happens
to observe going by. This is the app's first *active* feature: it goes
out and probes your LAN on demand rather than waiting for packets to
arrive. That's a meaningfully different trust/safety shape (it originates
new traffic instead of just watching), so I clarified scope with you
before building rather than guessing: you chose a combined table + node-map
display, a thorough ~1,000-port scan, auto-detected `/24` subnet, and a
one-shot manual-refresh scan (no continuous background scanning).

**How it works — two phases, both on a click of the new green "▶ SCAN"
button:**

1. **Host discovery.** Detects your active interface's `/24` (by opening a
   throwaway UDP socket toward a public address and reading back the local
   IP the OS picked — no packet is actually sent for this to work, it's
   just how the OS exposes "which interface would this go out of"), then
   pings every address in that `/24` in parallel (64 at a time). The pings
   themselves aren't trusted as the discovery signal — a firewalled host
   can silently drop ICMP while still answering ARP on the same LAN
   segment — so the pings exist only to *provoke* ARP resolution; the
   actual host+MAC list comes from reading back the OS's ARP table
   afterward (the same `arp -a` reader the app's existing passive MAC
   lookup already used).
2. **Per-host scan**, run host-by-host once discovery finishes:
   - **Ports:** a TCP connect-scan across 1,140 ports — all of well-known
     1–1024 plus a curated ~90 additional common high ports (databases,
     RDP, dev/web servers, NAS/IoT). I deliberately did not claim to
     reproduce nmap's frequency-ranked "top 1000" list — nmap isn't bundled
     with the app and I won't guess at a list I can't verify — so this is
     a transparent, broader superset instead.
   - **Hostname:** reverse DNS (PTR) first, wrapped in a hard timeout
     (Python's own `gethostbyaddr` has no built-in timeout, so it's run in
     a background thread with a bounded `join()`); if that comes back
     empty, falls back to a NetBIOS Name Service (NBSTAT) query on UDP/137
     for local Windows/SMB machines that don't have PTR records.
   - **MAC + vendor:** MAC from the same ARP read as discovery; vendor
     from the app's existing OUI vendor table.
   - Results stream into the UI host-by-host as they complete, not all at
     once at the end.

**UI:** a new dark-themed "LAN Scan" window (matching the Geo Map window's
look), opened by a new "🖧 LAN SCAN" button on the EtherApe toolbar.
Left side is a sortable table (IP, Hostname, MAC, Vendor, Open Ports, Last
Scanned). Right side is a 16×16 grid network map — one cell per possible
host on the subnet — with an orange dot for a live host with open ports, a
blue dot for a live host with none, and a white ring on whichever host is
currently selected; clicking either a table row or a map dot selects that
host and shows its full detail. Re-clicking the button while a scan is
already running/finished just brings the same window forward instead of
opening a second one. The in-app guide's EtherApe page has a new "LAN
Scan" section describing all of this, matching how the guide's been kept
in sync with every other new feature this session.

**Two real bugs found and fixed while testing this, not left for you to
find:**

- **Open-port count race condition:** the finished-scan status line
  ("Done — N host(s), M open port(s) total") was undercounting. The
  background scan thread was totaling ports by reading the UI's own result
  dict immediately after *scheduling* (not waiting for) the main-thread
  callbacks that actually populate it — a genuine cross-thread read race.
  Fixed by having the worker thread total the ports itself, from its own
  local results, instead of reading UI state back.
- **MAC address column too narrow:** caught only by looking at a rendered
  screenshot, not from any data-level test — the MAC column was 130px,
  which silently clipped the last character of a 17-character MAC address
  (`ttk.Treeview` clips without an ellipsis, so it just looks like a
  shorter, different-looking value). Four visually-distinct test MAC
  addresses all rendered as if identical. Widened the MAC column (and
  rebalanced the others) so full MACs render distinctly.

**Verified (not assumed):**

- Port scanner tested against real listening sockets, not mocks: opened
  three real local TCP listeners plus three known-closed ports and
  confirmed the scanner found exactly the three open ones, nothing more or
  less.
- NBNS (NetBIOS Name Service) parser tested with a synthetic constructed
  response packet round-tripped through the real encode/query/parse code
  (with the socket monkeypatched to hand back that packet) — confirmed the
  hostname comes back correctly. I have not tested this against a real
  Windows/SMB host, since this sandbox has no LAN to test against — see
  "Not done" below.
- Full UI/orchestration tested headlessly under `xvfb-run` with a real
  `EtherApeWindow` and real `_EtherApeScanWindow`, fed synthetic 4-host
  discovery/port/name data (the low-level primitives are what's tested for
  real above): confirmed the button opens the window, re-clicking reuses
  the same window instead of opening a second one, all 4 hosts land in
  both the table and the map, sorting works, table↔map selection sync
  works, the no-open-ports host shows an em-dash instead of blank or a
  crash, and — after the two fixes above — the port-total status line and
  the MAC column are both correct. A rendered screenshot after the fixes
  confirms this visually (sent alongside this changelog).
- `_NM_SCAN_PORTS` (the 1,140-port list) checked programmatically: no
  duplicates, sorted, exact count confirmed rather than assumed.
- `_nm_local_subnet()` and the ping-sweep/ARP-read path both run without
  crashing even in this sandbox, which has no real LAN and no `arp` binary
  — confirms they fail gracefully rather than assuming a working
  environment.
- Full `selftest.py`: 33/33 passed (Python 3.11, static + served-surface +
  JS checks, desktop checks skipped — no display) and 35/35 passed, 1
  skipped (Python 3.12 under `xvfb-run`, includes the desktop window and
  honeypot radar checks). No route content changed, so no re-baseline was
  needed.

**Not done / your call:**

- The NBNS fallback is implemented from protocol documentation and
  verified against a synthetic packet, but not against a real Windows/SMB
  host — this sandbox has no LAN to test against. If a host on your
  network doesn't resolve a hostname and you'd expect it to via NetBIOS,
  tell me and I'll dig into it with real data.
- This is a one-shot, manual-refresh scan, not continuous/background, per
  what you chose when I asked. Say if you'd rather it auto-rescan
  periodically.

## New: "[ BLOCKED ]" marker now sits on the actual blocked server, not floating in mid-canvas

**What you reported:** in the Topology window's Sankey ribbon view, the
red "[ BLOCKED ]" tag was floating somewhere in the middle of the canvas
with no clear line back to which external server it was actually about —
"its impossible to see whats blocked."

**Root cause:** the marker was drawn at the flow's arithmetic midpoint —
literally `((x0+x1)/2, (y0+y1)/2)`, halfway between the Internal Hosts
column and the External Servers column. With several flows converging
from different heights, that midpoint lands in empty space in the middle
of the canvas, not next to anything. Worse, every flow into the same
blocked host queued up its own separate marker at its own midpoint, so a
host with 3 blocked flows could show 3 overlapping tags nowhere near the
node itself.

**Fix:**

- The marker is now anchored at the blocked endpoint's actual on-screen
  position for that frame (`x1,y1` for a blocked destination, `x0,y0` for
  a blocked source) — the same coordinates the ribbon itself is drawn to
  in Sankey mode, i.e. the node's real column position, not the older
  radial-layout position — with a small downward offset so it sits just
  below the node's own name label instead of overlapping it.
- Markers are now collected in a dict keyed by the blocked IP instead of
  appended to a list, so multiple flows into the same blocked host collapse
  to exactly one marker instead of stacking duplicates on top of each
  other.
- The Geo Map window's separate "BLOCKED" mid-arc label (a different,
  genuinely geographic layout) was left as-is — your screenshots were
  specifically the Topology/EtherApe Sankey canvas ("Internal Hosts" /
  "External Servers" columns), not the map.

**Verified (not assumed):**

- Built the real `EtherApeWindow` headlessly under `xvfb-run`, switched it
  into Sankey mode, and fed it synthetic packets: 3 internal hosts all
  talking to one blocked external IP, a second blocked external IP with
  one flow, and a third, *unblocked* external IP with traffic of its own.
- Independently recomputed the Sankey column math (same formula as
  `_sankey_layout`, kept as a separate calculation in the test rather than
  reusing the app's own code, so the check can't just be confirming the
  code against itself) and asserted the actual rendered marker artists'
  positions against it: both blocked hosts got exactly one marker each,
  both at the External Servers column x-position and at that host's own
  row y-position plus the label offset — not at any midpoint. The
  unblocked external host correctly got no marker.
- First pass at this test compared marker position against
  `self._nodes[ip]['pos']` instead and got a mismatch — traced that to the
  test being wrong, not the fix: Sankey mode computes column positions on
  a local, shallow-copied dict inside `_render_tick_inner` and never
  writes them back to `self._nodes` (which keeps its original
  radial-layout position, used only by the Radial view). Rewrote the test
  to check against the same coordinates the ribbons themselves use, which
  is what actually matters for "does the marker sit at the node."
  Mentioning this because it's the kind of test-vs-fix mixup worth being
  upfront about rather than quietly correcting and moving on.
- Rendered a real screenshot of the fixed window (4 internal hosts, 1
  blocked external server with 4 converging flows, 3 unblocked external
  servers) — the "[ BLOCKED ]" tag sits directly under the blocked node,
  right where its own red-highlighted flows land, with no ambiguity about
  which server it's naming. Sent alongside this changelog.
- Full `selftest.py`: 33/33 passed (Python 3.11, static + served-surface +
  JS checks, desktop checks skipped — no display) and 35/35 passed, 1
  skipped (Python 3.12 under `xvfb-run`, includes the desktop window and
  honeypot radar checks). No route content changed, so no re-baseline was
  needed.

**Not done / your call:**

- Didn't touch the Geo Map's own mid-arc "BLOCKED" label — say if that one
  has the same "hard to tell which server" problem and I'll do the
  equivalent fix there using its real geographic arc endpoints.

## New: ISP Evidence Pack PDF now matches the app's dark theme

You asked for the Evidence Pack "themed like the rest of the app." It
was previously a plain white matplotlib PDF with default blue/purple/
orange lines — nothing like the dark navy + cyan interface everywhere
else. Now every one of its 8 pages uses the same dark palette as the
heatmap and quality windows (`#0a0e18` background, `#0d1828` panels,
`#38b8f0` cyan accents, `#c8dff0` body text, `#6a9ab8` muted labels),
and the three line charts (download/upload/ping) use your **actual
selected colour theme's** download/upload/ping colours — the same
three colours as the live gauges and dashboard charts — rather than
matplotlib's generic blue/purple/orange defaults.

Other changes to the pack:

- Section headers on the two text-summary pages (SERVICE AVAILABILITY,
  DOWNLOAD SPEED, PEAK-HOURS DOWNLOAD, UPLOAD SPEED, LATENCY / PING,
  METHOD & NOTES) now render in the accent cyan, and the ">> ..." callout
  lines (e.g. "Median is 27% below advertised") render in warning amber
  — both bold, so the things worth noticing actually stand out instead
  of being buried in a monospace wall of text.
- Outage bands on the time-series charts changed from a generic red to
  the same red used for danger states elsewhere in the app.
- Median lines are now green (good/reference), advertised-speed lines
  are amber (the threshold you're being compared against), matching the
  tip/warn colour meaning used throughout the rest of the UI.
- Chart legends are dark-boxed with light text instead of matplotlib's
  default white box, so they don't look like a mistake sitting on a
  dark chart.

**Verified (not assumed):**

- `python3 selftest.py` — 0 failures (route/api diff unaffected, this
  function isn't exposed over the web server).
- `xvfb-run -a python3.12 selftest.py` — full 35/35 pass + 1 skip.
- Actually **generated real PDFs** — not just read the code — using a
  synthetic in-memory SQLite database (400 fake readings, 2 fake
  outages, "Ocean" theme, advertised speeds set) and a second run with
  a different theme ("Neon"), no advertised speed configured, and zero
  outages, to exercise both the normal path and the edge cases (no
  advertised-speed comparison, empty outage log, no outage bands on the
  charts).
- Rasterized every page of both PDFs to PNG with `pdftoppm` and visually
  inspected all 16 renders: confirmed the dark background applies to
  every page (not just the charts), confirmed the download/upload/ping
  chart colours actually change with the selected theme (teal-green
  under "Ocean," bright green under "Neon"), confirmed section headers
  and callout lines pick up their accent colours (including catching
  and fixing a header-detection edge case — "DOWNLOAD SPEED (Mbps)"
  wasn't matching the "is this an all-caps header" check because of the
  lowercase "bps" inside the unit, so it stayed unstyled the first time
  through; fixed by ignoring parenthetical units when deciding what's a
  header), and confirmed nothing overlaps or clips on either the normal
  or edge-case data.
- **What I can't verify from here**: exact print/PDF-viewer rendering on
  your machine (fonts, viewer chrome) — the renders above are via
  `pdftoppm`/Poppler in this sandbox, not Windows' own PDF viewer or
  Acrobat. The colours and layout should be identical either way since
  it's the same PDF bytes, but worth a glance once you generate a real
  one.

## New: advertised-speed fields in Settings (ISP Evidence Pack)

You asked where `speedtest_config.json` lives, and I pointed out that its
`advertised_down`/`advertised_up` keys — used by the ⎙ Evidence Pack PDF
to show what % of your advertised speed you actually measured — had no
Settings UI, only a raw config-file edit. You then asked for a real
Settings field, so I added one.

New **"ISP Evidence Pack"** section in the ⚙ Settings dialog, between
"Speed Test Schedule" and "Tools" — two number fields, "Advertised
download" and "Advertised upload" (Mbps), pre-filled from the existing
config values, with a short note explaining what they're for and that
leaving both blank/0 skips the comparison in the pack. Saving writes
them back to `speedtest_config.json` as floats, same as every other
numeric setting in that dialog. The Evidence Pack generator itself
already read these two keys — this only adds the UI to set them; no
change to how the pack uses them.

While I was in that part of the file, I also fixed a stale line in the
in-app guide's Settings page — it said "five preset colour themes,"
but the app has had twelve (`Ocean, Sunset, Neon, Pastel, Mono, Crimson,
Arctic, Hacker, Purple, Gold, Fire, Ice`) for a while. Unrelated to the
Settings field, just noticed it while editing the same guide section
and it was a one-line fix.

**Verified (not assumed):**

- `python3 selftest.py` — the only route diff was `/guide` (its byte
  content changed because I edited guide text), which is exactly the
  intended change; re-baselined with `--update-ok`.
- `xvfb-run -a python3.12 selftest.py` — full 35/35 pass + 1 skip (skip
  is "no display," expected under plain `python3`).
- Built the real Settings dialog headlessly (Xvfb + a stand-in object
  with a `.config` dict, calling the actual `_open_settings_dialog`
  method) and screenshotted it — confirmed the new section renders in
  the right place, wraps its hint text correctly, and doesn't overlap
  neighboring sections. Screenshots taken both with the fields empty
  and pre-filled from a fake config (500/50), confirming existing
  values load into the boxes correctly.
- Simulated a real Save click on that headless dialog: typed 250/25 into
  the two new fields, invoked the actual Save button's command, and
  confirmed the fake config object ended up with
  `advertised_down: 250.0, advertised_up: 25.0` — the full UI-to-config
  round trip, not just that the widgets exist.
- Confirmed the build-ID bump alone changed zero routes (re-ran
  `selftest.py` after the bump, 0 failures).
- **What I can't verify from here**: how it looks on an actual Windows
  desktop at native DPI/font rendering — the screenshot above is from
  Xvfb on Linux, same caveat as every other UI change this session.

## The inetc auto-install (#21) failed on your machine — removed the plugin instead of chasing it

You ran `build_installer.bat` and got:

```
Plugin not found, cannot call inetc::get
Error in script "installer.nsi" on line 140 -- aborting creation process
```

That's exactly the failure mode I flagged as unverified in #21's caveat —
the plugin auto-download/placement I wrote couldn't be tested here (no
Windows machine, and this sandbox's own network can't reach the plugin's
download site either), and in practice it didn't work. I don't know
precisely which step failed on your machine (download, extraction, or
placement into the right `Plugins` subfolder) — the script's own cleanup
deletes its temp files whether it succeeds or fails, so there was nothing
left afterward to inspect.

Rather than guess at a second unverifiable patch to the plugin installer,
I removed the reason it's needed at all. `installer.nsi`'s four downloads
(Npcap, Wireshark, Ollama, librespeed-cli) used the `inetc` plugin's
`inetc::get` command. I rewrote all four to download via a small
generated PowerShell script (`Invoke-WebRequest`) run through NSIS's own
built-in `ExecWait` — no plugin involved at all. PowerShell and
`ExecWait` both ship with Windows 10 / NSIS respectively, so there's
nothing left to install, place, or get wrong. `build_installer.bat`'s
whole "check/install inetc" block from #21 is gone too — it has nothing
to do anymore.

One implementation detail worth knowing: `Invoke-WebRequest` has a
well-known performance bug where it renders a progress UI that can make
large downloads (Wireshark is ~90 MB) drastically slower unless
`$ProgressPreference` is set to `"SilentlyContinue"` first — every
generated download script sets that.

**Verified (not assumed):**

- Compiled the updated `installer.nsi` with **no NSIS plugins present at
  all** except the stock ones NSIS ships with (I didn't even install my
  usual `inetc` stub this time) — clean compile, 7 sections, 688
  instructions, no errors. This is the direct, concrete proof that the
  plugin dependency your build hit is actually gone, not just papered
  over.
- Re-verified parens/quotes balance in the batch file after removing the
  ~70-line inetc block (61/61 parens).
- Copied both files into `vanguard-flow-netsentinel` too.
- **What I still can't verify**: the actual `Invoke-WebRequest` downloads
  and Npcap/Wireshark/Ollama installs, same as before — no Windows
  machine here. This approach has less to go wrong (no plugin, no DLL
  placement, no zip-layout guessing for Npcap/Wireshark/Ollama), but
  please run it and tell me if anything still doesn't reach `[OK]` — I'd
  rather hear about a real failure than assume this one's right too.

## Speed-test CLI: installer now gets one automatically

You asked why the installer doesn't download a speed-test CLI. Answer:
it deliberately never bundles or downloads Ookla's own CLI — a call
already made in this codebase before I touched it, because Ookla's
licence forbids redistribution. But it also never downloaded either of
the two permissively-licensed alternatives the code already knew about
(`librespeed-cli`, LGPL, and `speedtest-cli`, Apache) — it just checked
whether you happened to already have one on PATH, and threw an error
telling you to install one yourself if not. So a fresh install could
genuinely have no working speed test until you did that by hand — a real
gap, not something I broke.

You asked me to fix it the same way as Wireshark/Npcap/Ollama. I did,
scoped to `librespeed-cli` only (still not touching Ookla's CLI — that
call stands):

- **`installer.nsi`** — new `SecSpeedtestCli` section. Skips itself if
  `librespeed-cli.exe`, `speedtest-cli` or `speedtest` is already
  reachable (checked with `where`, both via an existing local copy and
  on PATH). Otherwise downloads `librespeed-cli`'s official Windows
  release zip via `inetc::get`, then extracts it and copies the exe into
  `$INSTDIR` via a small generated PowerShell script rather than an
  inline `ExecWait` one-liner — `$INSTDIR`/`$TEMP` can contain spaces
  ("Program Files"), which is fragile to nest inside an
  already-quoted command. The extraction searches the unzipped tree
  recursively for `librespeed-cli.exe` rather than assuming the zip's
  internal folder layout, same defensive approach as the inetc-plugin
  fix above. Non-fatal on failure — warns and continues, same as the
  other three download sections.
- **`speedtest_monitor.py`** — `_nm_st_find()` (the function that locates
  a speed-test CLI at runtime) only ever searched PATH via
  `shutil.which()`. `$INSTDIR` is not on PATH, so the CLI the installer
  now places there would never have been found without this. Added a
  fallback: on a frozen/installed build, if nothing turns up on PATH,
  check for `librespeed-cli.exe` next to the running exe (exactly where
  the installer puts it). Reused the same fixed function for the
  module-level `SPEEDTEST_PATH`/`_DEFAULT_SPEEDTEST_PATH` default
  (previously duplicated similar-but-not-identical lookup logic inline)
  so the Settings dialog's displayed default is correct too, not just
  the runtime fallback path.

**Verified (not assumed):**

- Checked librespeed-cli's actual GitHub releases page (via the
  `expanded_assets` endpoint, since the normal release page loads assets
  with JS that a text fetch can't see) rather than guessing a filename —
  confirmed v1.0.14 current, exact asset name
  `librespeed-cli_1.0.14_windows_amd64.zip`.
- Compiled the updated `installer.nsi` end-to-end again with the same
  real NSIS 3.09 setup from the earlier fix (stub `inetc` plugin; `nsExec`
  is a stock NSIS plugin so needed no stub) — clean compile, 7 sections
  (up from 6), 712 instructions, no errors.
- While writing the `nsExec::ExecToStack` calls I made a real mistake —
  only popping the exit code and not the output string too, which would
  have corrupted the next `Pop` with stale stack data. Caught it myself
  before compiling by re-reading NSIS's documented `ExecToStack` stack
  contract (exit code, then output, output on top) and fixed it to pop
  both every time.
- `python3 selftest.py`: no web/API routes changed (expected — this
  touches only CLI-discovery code, nothing web-facing). `xvfb-run -a
  python3.12 selftest.py`: 35/35 green, 1 skip (the pre-existing
  no-tkinter-on-3.11 gap), same baseline as before — no rebaseline
  needed.
- **What I could NOT verify**: same caveat as the inetc-plugin fix —
  no Windows machine and no network path to github.com from this sandbox
  to actually run the download+extract+copy. Compiled and hand-checked
  carefully, but this is inference, not measurement, same as the inetc
  automation above. Try it once and tell me if the "Speed-test CLI"
  install step doesn't end in `[OK]`.
- Copied all three changed files (`installer.nsi`, `build_installer.bat`,
  `speedtest_monitor.py`) into `vanguard-flow-netsentinel` too.

## Build script: automated the manual NSIS inetc plugin step

You asked why installing the inetc plugin was a manual download-and-extract
step. Answer: NSIS itself does not ship inetc — it's a separate, very
widely-used third-party plugin (from the NSIS wiki, not the NSIS installer),
and `installer.nsi`'s `inetc::get` calls (the ones that fetch Wireshark,
Npcap and Ollama at install time) don't work until its DLL is dropped into
NSIS's own `Plugins\x86-ansi` / `Plugins\x86-unicode` folders. Until now,
`build_installer.bat` only ever *told* you to do that by hand (in the NSIS
build's error message) — it never did it.

Added a step, right after NSIS itself is detected, that:
- Checks whether `INetC.dll` is already sitting in either Plugins variant
  folder under the detected NSIS install — skips everything below if so.
- If missing, downloads `inetc.zip` from the official NSIS site (same
  curl-then-PowerShell-fallback pattern already used for Ollama).
- Extracts it and copies the DLL into the correct `Plugins\x86-ansi` /
  `Plugins\x86-unicode` folder(s) — matched by scanning the extracted
  filenames for "x86-ansi"/"x86-unicode", falling back to placing it in
  both if the zip's layout doesn't split them, so this doesn't hard-fail
  if the archive's internal layout isn't exactly what I expect.
- Re-checks afterward and prints [OK] or a [WARN] with the manual-install
  link, rather than silently pretending it worked.

**Verified (not assumed) — and one real caveat:**

- Confirmed the official download URL two ways: found it via the NSIS
  wiki's Inetc plug-in page (`https://nsis.sourceforge.io/mediawiki/images/c/c9/Inetc.zip`,
  81 KB) rather than guessing a sourceforge path.
- Could NOT execute this new batch+PowerShell code end-to-end — this
  sandbox has no Windows machine, and the sandbox's own network egress
  can't even reach sourceforge.io to fetch the real zip and test the
  extraction logic against real content (tried; connection refused).
  I hand-checked it carefully (parens/braces/quotes all balance; the
  curl/PowerShell-fallback shape mirrors the Ollama block already proven
  to work in this same file) but this is the one piece this session that
  is inference, not measurement. Please run `build_installer.bat` once
  and tell me if the "Checking for the NSIS inetc plugin" step doesn't
  end in `[OK]` — I'll fix whatever it gets wrong about the zip's layout.
- Copied the updated file into `vanguard-flow-netsentinel` too.

## Installer: Npcap URL bump + stale build-script banner

You asked for the installer to download dependencies from their official
sites instead of bundling them, to avoid redistributing other people's
software. I checked `installer.nsi` first rather than assuming — it
**already** does this for all three dependencies it installs (Wireshark,
Npcap, Ollama): each one is fetched at install time on the end user's PC
via NSIS's `inetc::get`, from the vendor's own site, not shipped inside
the installer. None of the third-party installer `.exe`s sitting in your
`setup` folder (Wireshark, npcap, nmap, MobaXterm, SQL Server Eval, etc.)
are referenced by `installer.nsi` at all — they're unused leftovers, not
things the installer bundles. (Same reason none of them made it into the
GitHub repo we set up.)

Two real problems I did find and fix, both in the download step itself:

- **Npcap URL was stale.** `NPCAP_URL` was pinned to `npcap-1.79.exe`.
  Checked npcap.com's live release listing: current is 1.88 (released
  2026-05-06). Updated the URL to `npcap-1.88.exe` and added a comment —
  unlike Wireshark, Npcap has no `-latest-` alias URL, so this has to be
  bumped by hand periodically; the comment says where to check.
- **`build_installer.bat`'s closing summary banner was wrong.** It told
  you "Ollama... To ship it to end users, add the same download/install
  step to installer.nsi" — implying that step was still needed, when
  `installer.nsi` has had a working `SecOllama` download section this
  whole time. Rewrote the banner to say what actually happens: Wireshark,
  Npcap and Ollama are all fetched fresh from their official sites on the
  end user's machine, not bundled.

**Verified (not assumed):**

- Installed a real NSIS 3.09 compiler in this sandbox (`apt-get install
  nsis`) and syntax-compiled the actual `installer.nsi` end-to-end —
  built a minimal stub `inetc` plugin DLL (via `mingw-w64`, since the
  Ubuntu NSIS package doesn't ship it) so the `inetc::get` calls would
  resolve. Compiled clean both before and after the edit: 6 sections, 648
  install instructions, no errors — confirming the script's structure and
  logic are sound, not just eyeballed.
- Confirmed no third-party binary sneaks into the output: with only stub
  placeholder files standing in for the app's own exe/assets, the
  compiled installer came out to ~343 KB — consistent with it containing
  only the app's own files, since nothing in the script embeds Wireshark,
  Npcap, Ollama, or any of the other `.exe`s sitting in the folder.
- Checked npcap.com's actual `/dist/` listing (not guessed) to confirm
  1.88 is current before hardcoding it.
- Checked the Wireshark download URL resolves to a large real binary
  (got a "response too large" fetch error, which is exactly what a
  90+ MB real installer looks like — not a 404 or redirect-to-nothing).
- Confirmed `https://ollama.com/download/OllamaSetup.exe` is the correct,
  current filename against Ollama's own docs, which reference
  `OllamaSetup.exe` by that exact name.
- Copied both fixed files into the `vanguard-flow-netsentinel` GitHub
  folder too, so the repo isn't left with the stale version.

## ISP Evidence Pack — fixed a crash on any missing/implausible reading

You sent a screenshot of the "ISP Evidence Pack" dialog failing with
`x and y must have same first dimension, but have shapes (298...` right
after picking a period and pressing Generate PDF.

**Root cause:** `_nm_evidence_pack()` builds one timestamp list (`ts`,
one entry per row) and separately builds `dls`/`uls`/`pgs` — the
download/upload/ping value lists — by filtering out implausible or
missing readings row-by-row. Each of those three lists is filtered
*independently*, so whenever even one reading anywhere in the period was
invalid (a negative/absurd speed, or a missing ping), the filtered list
ended up shorter than — and containing a different subset of rows than —
the unfiltered `ts`. The download/upload/ping time-series charts
(`ax.plot(ts, dls, ...)` etc.) then handed matplotlib two arrays of
different lengths, which is exactly the crash in the screenshot: 298 rows
in the period, but only some smaller number of valid download readings.
Even in the cases that happened not to crash (matching lengths by
coincidence), the same mismatch meant `zip(ts, dls)` — used for the
peak-hours split and the daily breakdown — was pairing each value with
the *wrong* timestamp, silently misreporting which hour or which day a
reading belonged to.

- Each metric now gets its own (timestamp, value) series — `dl_ts`/`dls`,
  `ul_ts`/`uls`, `pg_ts`/`pgs` — built in lockstep via a small `_series()`
  helper, so a bad download reading no longer discards a perfectly good
  upload/ping reading from the same row (more real data survives into the
  report, not less), and every list stays correctly paired with its own
  timestamps.
- The three time-series charts (download/upload/ping over time) now plot
  each metric against its own timestamp list instead of the unfiltered
  `ts`.
- The peak-hours (20:00–22:00) split and the daily breakdown now use the
  matching per-metric timestamp list instead of a shared `zip(ts, dls,
  uls, pgs)` that assumed all three were the same length and in the same
  order.
- Also fixed a related latent crash while in there: `max(dls)`/`min(dls)`
  (and the upload/ping equivalents) raise on an empty sequence, reachable
  if literally every reading for one metric in the whole period was
  invalid. Added a small `_max`/`_min` helper that falls back to 0.0
  instead of crashing — same defensive spirit as the fix above, same
  function, cheap to close off while already in this code.

**Verified (not assumed):**

- Reproduced the exact crash first: built a synthetic dataset of exactly
  298 rows (matching the row count in your screenshot) with a realistic
  mix of implausible download readings and missing upload/ping readings,
  ran the *old* filtering logic against it in isolation, and confirmed it
  throws `ValueError: x and y must have same first dimension, but have
  shapes (298,) and (280,)` — the identical error, not a guessed
  explanation.
- Ran the same 298-row dataset through the fixed `_nm_evidence_pack()`
  end-to-end (not a unit test of one function — the real PDF generation
  path) and confirmed it completes and writes a real PDF.
- Rendered the generated PDF to images and visually checked the download
  time-series page: the chart shows a continuous, correctly-scaled line
  with the median and advertised-speed reference lines, no gaps or
  artifacts from the dropped readings.
- Wrote a targeted alignment check with traceable, distinct per-row
  values: confirmed every surviving (timestamp, value) pair in the new
  `dl_ts`/`dls` series maps back to the correct original row — 0
  misalignments — and that exactly the expected count of rows was
  dropped.
- Checked the daily-breakdown page renders sensible per-day medians (not
  zeros or blanks) for a dataset with mixed valid/invalid readings.
- Tested the empty-series edge case directly: a dataset where every
  single download reading in the period was invalid — confirmed the fixed
  `_max`/`_min` helpers prevent the resulting empty-list crash and the PDF
  still generates.
- `python3 selftest.py` and the `xvfb-run -a python3.12` run: no served
  route content changed (this function is invoked from a desktop dialog
  and a PDF-download endpoint, not compared route content) and 35/35
  green (1 skip, same pre-existing gap as every build this session).
  Re-ran once more after the build-ID bump to confirm that alone changed
  no served route.

## Wireshark Monitor — Clear now actually deletes the capture file

You said running a capture and then clearing it was leaving huge files
behind instead of deleting them. This is the "Wireshark Monitor" window
(the one with Start Capture/Stop/Clear, `tshark -w`-ing live packets to
`%TEMP%\nm_wireshark.pcap`) — not the 3D/topology capture, which never
writes packets to disk in the first place and has nothing to leak.

**Root cause:** `_clear()` already tried to `unlink()` the pcap, but it did
so immediately, with no guarantee the tshark process (or its `dumpcap`
child, which does the actual capturing) had actually released the file
yet. `_stop_capture()`'s `.terminate()` only *asks* the process to exit —
it doesn't wait — so pressing Clear right after Stop (or pressing Clear
while a capture was still running, which the button never blocked) could
race a process that still had the file open. The delete's exception was
caught and silently swallowed, so the UI cheerfully said "Cleared" while
the multi-hundred-MB (or, per the existing 512MB auto-stop guard, up to
half-gigabyte) file just sat there.

- `_clear()` now, when a capture is (or was) running: stops it and
  **waits** for the process to actually exit (`proc.wait(timeout=3s)`,
  escalating to `kill()` if it doesn't) before attempting the delete —
  instead of firing terminate() and racing it.
- The delete itself now retries (4 attempts, 250ms apart) instead of
  giving up on the first failure, since a just-terminated process can take
  a moment to fully release its file handle even after `wait()` returns.
- If it still can't be deleted after all that, the status bar says so
  honestly ("...is still in use and could not be deleted; it will be
  removed next time this window opens" — which it will, via the existing
  startup stale-file cleanup) instead of claiming "Cleared" when it wasn't.
- New `_kill_capture_proc()` helper: on Windows, uses `taskkill /T /F`
  (kill the whole process tree) instead of a plain terminate(). tshark
  doesn't do the capturing itself — it spawns `dumpcap` as a child process
  to do that — and a bare `TerminateProcess()` on just the tshark parent
  (all `Popen.terminate()` does on Windows) can orphan that dumpcap child
  still holding the file open. This is a documented Wireshark/tshark
  behavior, not something specific to this app. Used both by the Clear
  path and by the existing MAX_CAPFILE_MB auto-stop guard, which had the
  same bare-terminate() gap.
- Added a small suppression flag so the background capture thread's normal
  "Capture stopped — N packets recorded" message (which fires asynchronously
  once the process's stdout closes) doesn't land a moment later and stomp
  the "Cleared" status Clear just set.

**Verified (not assumed):**

- Instantiated the real `WiresharkWindow` class (stubbing only the Tk
  widgets, not the logic) under `xvfb-run` and exercised the real methods
  against real subprocesses and real files — not a code-reading exercise.
- Spawned a real child process that holds the capture file open and delays
  0.6s before exiting on SIGTERM (simulating a capture process that
  doesn't die instantly): confirmed `_stop_capture(wait=True)` genuinely
  blocked for ~0.6s (matching the handler delay, not returning early) and
  that the process was confirmed exited (`proc.poll()`) before the method
  returned.
- Forced a **real** delete failure using `chattr +i` (immutable flag,
  which produces a genuine `PermissionError` even for root — Linux has no
  exact equivalent of Windows' open-file locking, so this is the closest
  faithful stand-in available in this environment) that clears itself
  mid-retry: confirmed the first attempts genuinely failed (real tracebacks
  logged), the retry loop recovered once the lock lifted, and the file was
  actually gone afterward.
- Repeated that test with the lock never lifting: confirmed all 4 attempts
  genuinely failed and the status bar reported the honest "still in use,
  could not be deleted" message with the real file size — not a false
  "Cleared" — and that the file was still present (matching real behavior,
  not a guess).
- Confirmed `_on_ended()` does not overwrite the "Cleared"/failure status
  when triggered by a Clear-initiated stop, and that the suppression flag
  correctly resets itself for the next real Stop button press.
- Being transparent about a limit: the Windows-specific `taskkill /T`
  dumpcap-orphan fix is based on well-documented tshark/dumpcap behavior,
  not something I could empirically trigger from this Linux sandbox (no
  Windows tshark available to test against) — flagging that distinction
  rather than presenting it with the same confidence as the parts above
  that I did directly exercise.
- `python3 selftest.py`: zero routes changed (this is a desktop-only
  Tkinter window, not served over HTTP, so that's expected, not a
  false-negative) — same result under `xvfb-run -a python3.12`, 35/35
  green (1 skip, same pre-existing gap as every build this session). No
  re-baseline needed since nothing web-facing changed. Re-ran once more
  after the build-ID bump to confirm that alone changed no served route.

## 3D view — GRID toggle button

You asked for a button to toggle the grid in the 3D view. Added a GRID
button to the toolbar, next to LABELS, matching the existing SPREAD/
BLOCKED/LABELS toggle-button convention exactly (same `.tbtn`/`.tbtn.active`
styling, same on-by-default look SONAR already uses elsewhere in this app).

- Scope: "the grid" means the `GridHelper` line grids specifically — the
  floor grid plus the 4 wall grids (built in the same room-construction
  block covered earlier this session). The solid floor fill and the
  translucent glass wall panes are separate decorative meshes and are
  unaffected — toggling GRID removes just the line pattern, not the room
  itself or the starfield showing through the glass.
- The 4 wall `GridHelper`s were previously built and added to the scene
  without being kept in any accessible variable (each was a local `const g`
  inside a `forEach`, thrown away after `scene.add(g)`). Added a top-level
  `_wallGrids` array and pushed each one in, so all 5 grid meshes (floor +
  4 walls) can be found and toggled together.
- `toggleGrid()` flips `_gridVisible`, sets `.visible` on the floor grid
  and all 4 wall grids, and toggles the button's `active` class — same
  shape as the existing `toggleLabels()`/`toggleShowBlocked()` functions
  right next to it.

**Verified (not assumed):**

- `node --check` on the extracted `/3d` script block: valid.
- Drove the real `/3d` route in headless Chromium with synthetic node/flow
  data, then read `grid.visible`, `_wallGrids.map(g=>g.visible)` and the
  button's `className` directly from the live page both before and after
  — confirmed default state is all-visible with the button showing
  `active`.
- Clicked the actual `#btnGrid` element (not calling the JS function
  directly) to prove the click handler is wired correctly, and confirmed
  all 5 grid meshes flipped to `visible:false` and the `active` class was
  removed; clicked again and confirmed everything flipped back.
- Screenshotted before and after the click: the floor and wall grid lines
  visibly disappear together while the packet console panel, starfield,
  and room silhouette (from the glass panes / floor fill) stay exactly as
  they were — confirming the toggle is scoped to just the grid, not a
  side effect on anything else.
- `python3 selftest.py`: only `/3d` changed (194940 → 195612 bytes), every
  other route byte-identical; re-baselined with `--update-ok` under
  `xvfb-run -a python3.12`, 35/35 green (1 skip, same pre-existing gap as
  every build this session). Re-ran once more after the build-ID bump to
  confirm that alone changed no served route.

## Honeypot — higher trap rate + more decoy ports

You said "increase the honeypot's trap rate and add more decoy connections
to slow down attackers." Both parts of that were ambiguous enough to ask
rather than guess (the honeypot already tarpits every hit by default, so
"trap rate" isn't a probability knob — it had to mean capacity or duration),
and you picked: raise the concurrent-tarpit cap, hold each connection
longer, and add more decoy ports/services. Auto-block threshold (currently
2 hits) was explicitly left alone — you didn't select that option.

- `TARPIT_HOLD_SECONDS`: 180.0 → 600.0 (3 min → 10 min per held connection).
- `MAX_TARPIT_CONNS`: 150 → 400 (hard cap on how many scanners can be held
  open at once before the cap turns new ones away immediately instead).
- `TARPIT_BYTE_DELAY` (2–6s between drip bytes) left unchanged — you didn't
  ask for the drip itself to get slower, just for more capacity and a
  longer hold.
- Five new TCP decoy ports added to `_NM_HONEYPOT_PORTS`: 2222 (SSH-alt,
  reuses the real SSH banner since it's the same protocol on an alt port),
  8443 (HTTPS-alt), 5984 (CouchDB), 2375 (Docker API), 502 (Modbus/ICS —
  privileged port, needs admin/root to bind, same as the existing sub-1024
  decoys). 15 → 20 TCP decoy ports; the 10 UDP decoys are unchanged. All
  five were picked because a connection to any of them from outside is
  essentially never legitimate on a desktop, same reasoning as every
  existing port on the list.
- `/guide`'s Honeypot section updated: the decoy-port paragraph now
  mentions the new services, and the Tarpit bullet's numbers changed from
  "3 minutes... capped at 150" to "10 minutes... capped at 400". The web
  console and desktop window both build their port-count text from the
  same dict at request time, so they picked up the new ports automatically
  with no template changes needed.

**Verified (not assumed):**

- Confirmed at runtime (not just read from source) that all five new ports
  are in `_NM_HONEYPOT_PORTS`, the 2222 banner is registered, the TCP
  decoy count is 20, and `_NMHoneypot.MAX_TARPIT_CONNS`/`TARPIT_HOLD_SECONDS`
  read 400/600.0.
- Started a real `_NMHoneypot` on real loopback sockets bound to the four
  unprivileged new ports (2222, 8443, 5984, 2375) with hold/delay
  constants compressed for a fast test (same code path, shorter numbers —
  same technique used earlier this session for the original tarpit work)
  and connected real client sockets to each: all four produced real hit
  records with the correct service label (SSH-alt/HTTPS-alt/CouchDB/Docker
  API).
- Separately bound port 502 (the one privileged new port, <1024) with a
  real socket and confirmed it actually binds under this environment's
  root privileges, exactly like the existing sub-1024 decoys (SSH/Telnet/
  FTP/SMTP/SMB) already required.
- Tarpit-held one of the new ports end-to-end with a real client socket:
  measured real drip bytes actually arriving (25 bytes of the one-byte-at-
  a-time drip) and the connection stayed open for the held duration before
  the server closed it — confirming the new ports run through the exact
  same `_tarpit()` path as the original ones, not a bypass.
- `python3 selftest.py`: only `/guide` changed (64995 → 65137 bytes, the
  updated Honeypot section text); every other route byte-identical
  including `/honeypot` itself (that page renders live hit history, which
  is empty with nothing connected during the static selftest fetch — not a
  sign the new ports are missing from it). Re-baselined with
  `--update-ok` under `xvfb-run -a python3.12`, 35/35 green (1 skip, same
  pre-existing no-`tkinter`-on-3.11 gap as every other build this
  session). Re-ran once more after the build-ID bump to confirm that alone
  changed no served route.

## 3D view — packet console lowered on the left wall

You said "needs to be lower" right after the console landed on the left
wall at `(-29.85, 16, 0)` (bottom edge at y=8.5). Dropped it:
`position.y` changed from `16` to `7.5`, moving the bottom edge from y=8.5
down to y=0 — roughly 6 units of clearance above the floor (y=-6) instead
of over 14. Nothing else about the mount changed: same `rotation.y =
Math.PI/2`, same `26×15` scale, same x/z placement flush on the wall.

**Verified (not assumed):**

- Checked the mesh's actual world-space bounding box after the edit
  (`THREE.Box3().setFromObject(_pktMesh)`): y now spans 0 to 15, confirming
  the drop landed where intended and the bottom edge still clears the
  floor rather than clipping into it.
- Screenshotted head-on from inside the room at the new height (`panY`
  matched to the new centre) — panel still fully legible, correctly
  oriented, same colour-coded rows.
- Screenshotted a natural three-quarter angle showing the floor, the
  wall/floor corner, and the panel together — visibly lower against the
  wall now, still floating clear of the floor with a visible gap, no
  clipping.
- `python3 selftest.py`: only `/3d` changed (194902 → 194940 bytes), every
  other route byte-identical; re-baselined with `--update-ok` under
  `xvfb-run -a python3.12`, 35/35 green (1 skip, same pre-existing
  no-`tkinter`-on-3.11 gap as always). Re-ran once more after the build-ID
  bump to confirm that alone changed no served route.

## 3D view — packet console moved to the left wall

You said "put it on the left wall instead" about the packet-capture console
that was lying flat on the floor. "Left" needed a definition rather than a
guess: with the room's default camera (`rotY=0`, standard Three.js
right-handed convention, no roll), the camera sits at positive Z looking
back toward the origin, and screen-right corresponds to world +X — so
screen-left is world **-X**, which is the room's west wall (`x=-30`), the
same wall the room-building code already treats as one of the four glass
walls.

- `_pktMesh` (the same canvas-texture plane, same `_pktRedraw()`/
  `_pktEmit()` row logic — none of that changed) is now mounted flush
  against the west wall instead of lying on the floor: `rotation.y =
  Math.PI/2` (the exact convention the room's own `glassPane()` helper
  already uses for its East/West wall panes, so the console's front face
  points +X, into the room, the same direction the wall's own glass faces),
  positioned at `(-29.85, 16, 0)` — just off the wall plane to avoid
  z-fighting with the glass, centred along the wall's 60-unit length, and
  at a height (spans roughly y=8.5 to y=23.5) comfortably above the floor
  and well inside the wall's y=-6..54 span.
- Added `side:THREE.DoubleSide` to the panel's material, matching
  `glassPane()`'s own walls, so it doesn't vanish if the camera ever drifts
  slightly past the wall plane.
- Removed the now-unused `FLOOR_LINE_Y` constant (and the temporal-dead-
  zone-avoidance comment that went with it) since nothing floor-anchored
  reads it anymore.
- `_pktMesh.visible=!WORLD_ON` (hidden in globe mode) and the gentle
  opacity-shimmer in `animate()` are untouched — both are transform-
  independent and needed no changes.

**Verified (not assumed):**

- Confirmed via `node --check` that the edited `/3d` script block still
  parses cleanly.
- Drove `rebuildGeometry()` with a synthetic 9-node topology and
  `_pktEmit()` through the real `/3d` route in headless Chromium, then
  positioned the camera to look squarely at the west wall from inside the
  room (`panX=-15, zoom=25, rotY=Math.PI/2`) — screenshotted and confirmed
  the console renders flush against the wall, fully legible, correctly
  coloured per protocol, with rows reading left-to-right in the correct
  order (not mirrored).
- Cross-checked the "front face" claim by also screenshotting from
  *outside* the wall looking back in (`rotY=-Math.PI/2`, camera beyond
  `x=-30`) — as expected for a single-normal plane, the text there reads
  mirrored/reversed, confirming the front (readable) face genuinely points
  into the room and the mount isn't flipped.
- Screenshotted a natural three-quarter angle from inside the room (not a
  head-on shot) — the panel sits correctly in the wall/floor corner with no
  clipping through the floor or the glass, and stays legible in perspective.
- `python3 selftest.py`: only `/3d` changed (194795 → 194902 bytes), every
  other route byte-identical; re-baselined with `--update-ok` under
  `xvfb-run -a python3.12`, then confirmed 35/35 green (1 skip — no
  display's `tkinter` on the 3.11 interpreter, pre-existing, unrelated).
  Re-ran once more after the build-ID bump to confirm that alone changed no
  served route.
- Did **not** get a clean confirmation shot from the default (un-panned)
  camera — in this sandbox today, screenshots taken without an explicit
  camera override came back showing an empty room (no nodes, no grid,
  nothing) regardless of wait time, and the same happened when I re-ran an
  earlier, already-delivered build's identical test script against a fresh
  server — so it's a pre-existing Playwright/sandbox rendering quirk in
  today's environment, not something this change introduced. Flagging it
  here rather than papering over it: the explicit-camera shots above are
  real renders of the live scene, not a workaround for a broken feature.

## 3D view — floor redone as a live scrolling packet-capture console

You said "nope" to the glowing flow-path floor and sent a reference clip of
an actual Wireshark-style capture table — scrolling rows of No./Time/
Source/Destination/Protocol/Len/Info, colour-coded by protocol. Before
building I confirmed two things rather than guess: (1) replace the flow-path
lines entirely rather than keep both, and (2) since this app's 3D view only
has aggregated flow data — not individual captured packets — the row
columns would use real data everywhere real data exists (time, source,
destination, protocol, length), with the "Info" column using honest
protocol-appropriate template wording instead of fabricated specifics like
fake sequence numbers. You confirmed both.

- Removed entirely: `floorLines`/`floorParts` and everything that fed them
  (the `FLOOR_PARTS_PER_FLOW`/`FLOOR_MAX_PARTS` buffers, the floor-projection
  loop in `rebuildGeometry()`, the floor-shadow particle block in
  `animate()`). Nothing left half-wired.
- New packet console: a canvas (No./Time/Source/Destination/Proto/Len/Info
  columns, glowing cyan frame) rendered to a `CanvasTexture` on a
  `PlaneGeometry` laid flat on the floor like a screen embedded in the
  ground — `_pktMesh`, built once in the same setup block the old floor
  geometry used to live in.
- New rows come from `_pktEmit()`, called from `poll()` every time fresh
  flow data arrives (~every 600ms) — every column but Info is real: `time`
  is the real elapsed session clock, `src`/`dst`/`proto` come straight off
  the flow, `len` is the real average bytes-per-packet for that flow
  (`bytes/pkts`, not invented). Which flows get a row that tick is weighted
  by real packet count — a flow carrying more traffic produces more log
  lines, same as a real capture would, not fixed round-robin. `Info` uses
  `PKT_INFO`, a small per-protocol template table (e.g. "Application Data"
  for TLS — which is genuinely what real Wireshark shows for encrypted
  payloads since it can't see inside; "Echo (ping) request" for ICMP);
  blocked flows show "Blocked by firewall", suspicious ones get a
  "[flagged]" suffix. Row list caps at 18 and drops the oldest, redrawing
  the canvas only when rows actually change — not a per-frame cost.
- Hidden in globe (World View) mode via the same `_pktMesh.visible=!WORLD_ON`
  pattern the rest of the floor furniture uses — there's no flat floor to
  read a console off of once the room becomes a planet.

**Verified (not assumed):**

- Drove `rebuildGeometry()` + repeated `_pktEmit()` calls with a synthetic
  10-node topology through the real `/3d` route in headless Chromium (no
  live capture in this sandbox) and screenshotted from both a three-quarter
  angle and straight down — confirmed the console renders as a legible,
  colour-coded table matching the reference clip's layout, sitting flat on
  the floor under the live topology.
- Checked realism, not just appearance: called `_pktEmit()` on a real
  600ms cadence (matching `poll()`'s actual interval) instead of a tight
  loop, then read `_pktRows` back out directly — confirmed `time` values
  genuinely increase tick to tick, `no` increments monotonically, and the
  row list caps at exactly 18 with the oldest evicted.
- Confirmed the World View guard: toggled `toggleWorld()` live and read
  `_pktMesh.visible` directly — `false` the instant globe mode turns on.
- Checked the browser console across a full page load: no new errors (the
  one pre-existing, unrelated 404 from earlier builds is still there,
  untouched by this change).
- `selftest.py`: 35/35 green on Python 3.12 under `xvfb-run` (1 skip, same
  as always). `/3d` was the only route whose content changed; re-baselined
  with `--update-ok` and confirmed clean. JS syntax check (10 script
  blocks) stayed clean throughout, and a `grep` for the removed
  `floorLines`/`floorParts`/`FLOOR_PARTS_PER_FLOW`/etc. identifiers came up
  empty — no dangling references left behind by the removal.

## 3D view — floor animated with real packets travelling through the flows

You sent another reference clip (an abstract glowing data/code mood video)
and asked for the floor to be animated showing packets going through the
flows. Since the clip is a mood reference rather than a literal blueprint,
I proposed four concrete directions — floor-projected flow paths, a radar
sweep + pulse rings, sweeping ambient light beams, or a combo — and you
picked floor-projected flow paths: real traffic, not decoration.

- Each active flow now gets a straight glowing line drawn directly on the
  floor grid, connecting the ground point under its source to the ground
  point under its destination — literally the same source/destination
  positions used by the real 3D arc above it, just flattened onto the
  floor. `blocked` flows still render red, everything else keeps its
  protocol colour, exactly like the arcs.
- Small bright dots continuously travel along each floor line, sampled
  from the *exact same curve and `u` progression* as the real arc
  particles floating above — so a floor dot is the genuine ground shadow
  of a real packet's position, not an independently-timed decoration.
  Same per-flow speed formula as the arc particles (busier flow = faster),
  so the floor and the topology above it always agree.
- New geometry only: `floorLines` (a `LineSegments`, mirrors the existing
  `flowLines`) and `floorParts` (a `Points` layer, mirrors the existing arc
  particles but with 2 dots per flow instead of 4, and no trail-echo
  layers — meant to read as a quiet map under the main scene, not compete
  with it). Both populate in `rebuildGeometry()` and animate in `animate()`
  right next to the code they mirror.
- Hidden entirely in globe (World View) mode — there's no flat floor to
  project onto once the room becomes a planet, so `rebuildGeometry()` zeroes
  both draw ranges and hides both meshes whenever `WORLD_ON` is true, and
  restores them on switching back.

**Verified (not assumed) — including a real bug caught immediately:**

- First test run crashed the whole 3D view on load: `ReferenceError:
  Cannot access 'FLOOR_Y' before initialization`. The new floor-geometry
  setup sits near the top of the script (next to the existing flow-line
  setup it mirrors), but `FLOOR_Y` isn't declared until much further down,
  in the protocol-bars section — a temporal-dead-zone violation, not a
  typo `node --check` would catch. Fixed by using the literal `-5.95`
  (documented as `FLOOR_Y + 0.05`) instead of referencing the not-yet-
  initialized const.
- Drove the real `rebuildGeometry()`/`animate()` code path with a
  synthetic 10-node, 10-flow topology (since there's no live capture in
  this sandbox) and screenshotted from both a three-quarter angle and
  straight down — confirmed the floor lines radiate correctly from the
  local host's ground position to each remote host's, coloured per
  protocol, with visible dots on each line.
- Confirmed genuine motion, not a static frame: six-frame rapid screenshot
  sequence, cropped to the floor area — each dot's position along its line
  visibly advances frame to frame, staying on its line the whole time.
- Confirmed the World View guard actually works: toggled `toggleWorld()`
  live and checked `floorLines.visible`/`floorParts.visible` directly —
  both flip to `false` the instant globe mode turns on.
- Confirmed the empty-state teardown: cleared all node/flow data and
  watched both the floor lines/dots and the floating topology disappear
  together — nothing left glowing with no data behind it.
- Checked the browser console across a full page load: no new errors (the
  one pre-existing, unrelated 404 from before this build is still there,
  unrelated to any of tonight's changes).
- `selftest.py`: 35/35 green on Python 3.12 under `xvfb-run` (1 skip, same
  as always). `/3d` was the only route whose content changed; re-baselined
  with `--update-ok` and confirmed clean. JS syntax check (10 script
  blocks) stayed clean throughout.

## 3D view — protocol bars redone as scrolling neon circuit traces

You didn't like the traveling-pulse look from the previous build and sent a
reference clip: a glowing blue/purple "digital graph" pattern made of dense,
sharp right-angle neon traces. Replaced the pulses with that instead — same
contract as before (bar length/legend/labels untouched, animation is purely
additive), just a completely different visual for the "alive" part.

- New `_makeCircuitCanvas()`: draws three stepped, glowing neon lines (cyan,
  blue, purple) with right-angle jogs, three-pass glow (wide/soft → tight →
  bright core) per line, on one shared canvas. Each protocol bar wraps that
  same canvas in its own `CanvasTexture` (cheap — shared pixels, independent
  wrap/repeat/offset), replacing the small traveling blocks entirely.
- Each bar now carries a thin overlay riding on top, textured with that
  pattern and continuously scrolled along the bar's length — tile density
  held constant in world-units regardless of the bar's current (eased)
  length, so the trace pattern doesn't stretch or squish as it grows/shrinks.
  Scroll speed and visibility are still driven by that protocol's live flow
  count and still fade to nothing at zero, same as the pulses did.
- Dimmed the base bar itself (`emissiveIntensity` 0.55→0.20, `opacity`
  0.9→0.5) — with the old brighter bar, the neon overlay just blew out to a
  flat white glow on top of it instead of reading as distinct coloured
  lines; the bar now reads as a quiet "track" and the scrolling trace is the
  one bright, animated thing on it.

**Verified (not assumed) — including a real bug caught mid-build:**

- First pass looked wrong on screen: the overlay rendered as a smeared solid
  glow with no visible line detail, not the neon traces from the canvas.
  Dumped the raw canvas via `toDataURL()` to confirm the texture itself was
  correct (it was — clean 3-colour stepped lines), so the bug was in how it
  mapped onto the bar. Patched a single bar's texture live in the browser
  console to test `repeat.y`/`wrapT` instead of `repeat.x`/`wrapS`, screenshot
  it, and confirmed THREE's default box UVs put V — not U — along this box's
  Z axis (the bar's length): the first version was tiling the pattern 6+
  times across the bar's ~1-unit WIDTH, which just minified into a blur,
  while the LENGTH axis carried a single non-repeating stretch. Rewrote the
  canvas (tall, not wide) and swapped both the wrap axes and the per-frame
  `repeat`/`offset` calls to match; re-screenshotted top-down and got the
  intended clean repeated zigzag bands running the bar's full length.
- Confirmed genuinely scrolling, not just present: same six-frame rapid
  screenshot sequence technique as the traveling-pulse build, cropped to one
  bar — the zigzag step positions visibly shift frame to frame.
- Re-checked the zero-traffic case after all of the above changed: bars
  ease back down, legend greys out, overlays fade out with them — nothing
  left glowing with no data behind it.
- Checked the browser console across a full page load for JS errors: none
  (one pre-existing, unrelated 404 for a static resource, present before
  any of this session's changes too).
- `selftest.py`: 35/35 green on Python 3.12 under `xvfb-run` (1 skip, same
  as always). `/3d` was the only route whose content changed; re-baselined
  with `--update-ok` and confirmed clean. JS syntax check (10 script
  blocks) stayed clean throughout.

## 3D view — traveling light pulses on the protocol bars

You said the floor bars were "a bit boring" and asked how to animate them
better without losing functionality. I proposed four directions (traveling
pulses, event-driven flash, vertical equalizer bars, or a combo) and you
picked traveling pulses. Implemented in `/3d`; nothing about what the bars
*mean* changed.

- Each bar now carries up to 4 small bright streaks that continuously
  travel from the row (where the label sits) out to the bar's tip, on a
  loop, riding on top of the existing extruded box — the box itself still
  does 100% of the "length = byte share, presence = has live flows" job it
  always did.
- How many streaks are running and how fast they travel is driven by that
  protocol's live flow count (`bar.liveN`, computed in `updateProtoBars`
  from the same flow list that already feeds the length/legend): busier
  protocols get more, faster streaks; a protocol with zero live flows gets
  none, at all — so the animation itself is a second read of activity, not
  just decoration.
- The whole streak layer eases in/out with a `pulseAmt` value (same 0.10
  lerp cadence as the bar length) so a protocol going quiet→active or back
  ramps smoothly instead of streaks popping in/out.
- Streaks are separate `MeshBasicMaterial` boxes (additive blending, no
  depth write) tinted a lightened version of the bar's own colour, so they
  read as "hot" highlights riding the bar rather than a different colour
  fighting it. Pre-allocated 4 per bar at build time and toggled
  `.visible` per frame rather than created/destroyed on every poll.
- Untouched: bar geometry/position, the base pad for empty protocols, bar
  labels, the `#legend` panel (exact percentages/counts), and the fact
  that none of this is in `_rayTargets` — still purely decorative, still
  can't intercept a click.

**Verified (not assumed):**

- Ran the real `/3d` route in headless Chromium again, this time driving
  `updateProtoBars()` directly with synthetic flow lists (varied protocols,
  varied live-flow counts) since there's no live capture in this sandbox —
  confirmed real code path, not a mock of it.
- Sampled a bar's pulse meshes' live `position`/`opacity`/`visible` values
  directly from the page and confirmed streaks sit within the bar's actual
  current (eased) length and fade at both ends as designed.
- Took a rapid screenshot sequence (six frames, ~280ms apart) from a
  grazing side-on angle down one bar, cropped to just that bar, and
  stacked the frames — the bright streak visibly shifts position frame to
  frame, confirming it's genuinely traveling, not a static bright patch.
- Fed in zero flows after establishing traffic and confirmed on screen:
  bars ease back down, the legend greys out to `—` for every protocol, and
  every streak fades out and disappears along with the bar — nothing gets
  stuck visible with no data behind it.
- `selftest.py`: 35/35 green on Python 3.12 under `xvfb-run` (1 skip,
  same as always). `/3d` was the only route whose content changed;
  re-baselined with `--update-ok` and confirmed clean. JS syntax check (10
  script blocks) stayed clean throughout.

## 3D view — sparkle-flare starfield + glass walls

You sent two reference images (a dense night sky of glowing four-point
sparkle stars, mostly blue-white, on a deep navy gradient) and asked for
the 3D view's star animation to look like that, plus the four room walls
to match the floor's colour but "obviously transparent" so the stars
show through. Both done in `/3d`.

**Stars:**

- Two new canvas-generated textures: `_makeDotSprite()` (a soft round
  glow, used for the existing bulk star layer) and `_makeFlareSprite()`
  (a proper four-point sparkle — radial glow halo + two crossed spike
  gradients + a bright core), matching the reference image's star shape
  rather than the plain dots the view had before.
- Bulk starfield bumped from 2600 to 3200 points, now uses the new dot
  texture with additive blending instead of flat circles.
- New "hero stars" layer: 150 individually-placed sprites using the
  flare texture, scattered on the same shell as the bulk field, ~85%
  white / ~15% cool blue, each with its own random size, base opacity,
  twinkle speed and phase.
- New per-frame twinkle in `animate()`: each hero star's opacity and
  scale ease in and out on its own sine clock, so the "star animation"
  actually animates (independent twinkling) rather than sitting static.

**Walls:**

- Added a `glassPane()` helper alongside the existing wall grids: a
  solid backing plane per wall, same colour as the floor's own fill
  (`0x070f1c`), `opacity:0.16`, double-sided, `depthWrite:false` — mirrors
  the floor's own "grid lines + solid backing" construction, just with
  the backing made translucent instead of opaque, so the starfield glows
  through the walls instead of the room reading as a closed box.

**Verified (not assumed):**

- Ran the actual `/3d` route in a real headless Chromium (Playwright,
  software WebGL) against a live instance of `_ThreeDServer`, not just
  read the code. First pass: the new stars were completely invisible on
  screen despite building without errors. Isolated the cause with a
  series of controlled A/B sprites/points added directly into the live
  scene: confirmed the flare texture itself was correct (a close-up test
  sprite rendered exactly the intended four-point sparkle), and traced
  the real bug — the 150 hero-star sprites were placed ~620–800 world
  units from the camera but sized only 3–8 world units, far too small to
  read at that distance under normal perspective (a `Sprite`'s scale is
  a world-unit size that shrinks with distance, unlike the
  `sizeAttenuation:false` points used for the bulk field, which stay a
  constant screen size). This would have been invisible on real hardware
  too, not just the sandbox's software renderer — fixed by resizing hero
  stars to 7–53 world units, skewed toward small with occasional large
  bright ones.
- Re-screenshotted after the fix from several camera angles (a close default
  view, a wide three-quarter room view, and a low upward-looking view) and
  visually confirmed: hero stars now render as clear four-point sparkles
  of varied size and brightness against the navy field, closely matching
  the reference images; the wall grid + glass tint is visible with stars
  showing through it; the floor and walls read as the same colour.
- Confirmed the twinkle animation is actually animating, not just a
  static frame: sampled five hero stars' live `opacity`/`scale` values
  three times, 1.5s apart, and confirmed every one was smoothly changing
  between samples.
- `selftest.py`: on Python 3.12 under `xvfb-run`, 35/35 green (1 skip,
  same as always). `/3d` was the only route whose content changed
  (expected — the whole point of the change); re-baselined with
  `selftest.py --update-ok` and confirmed clean against the new
  baseline. Every other route byte-identical, so nothing else leaked.
  JS syntax check (10 script blocks) stayed clean throughout.

## Merged the two `_NM_OUI` tables

You said "yes merge" to the duplicate-`_NM_OUI` issue flagged at the end
of the firewall-names work. Done.

There were two module-level dicts both named `_NM_OUI` — one near the
device-inventory code (§4, used by `_nm_device_name` and the new firewall
names feature), one much further down next to `_nm_load_oui`/
`_nm_oui_vendor`. Python just keeps whichever assignment runs last at
import time, so the second one silently won and the first one's 7 unique
entries were dead code the whole time: `00:1d:d8`/`00:50:f2` (Microsoft),
`3c:07:54` (Apple), `52:54:00` (QEMU/KVM), `00:04:4b`/`48:b0:2d` (NVIDIA),
`d8:6c:63` (Google).

Two prefixes were in both dicts with genuinely different values — not
just formatting differences:

- `00:15:5d`: `'Hyper-V'` vs `'Microsoft Hyper-V'` — same product, kept
  the more descriptive one.
- `d8:3a:dd`: `'Sonos'` vs `'Raspberry Pi'` — a real conflict, not
  cosmetic. Checked against a live OUI vendor lookup rather than guessing
  which curated entry was stale: **Raspberry Pi Trading Ltd** is the
  registered vendor, so `'Sonos'` was simply wrong and has been dropped.

Merged into a single 60-entry `_NM_OUI` at the original (§4) location,
grouped by vendor for readability. Deleted the second definition and left
a comment pointing back to the merged one, so this can't silently
reappear the same way. `_nm_oui_vendor()` — the function that actually
gets called for most vendor lookups elsewhere in the app, which checks
the full downloaded IEEE database first and only falls back to this
curated table — is untouched and now benefits from the same fix
automatically, since it reads the same `_NM_OUI` global.

**Verified:** parsed both original dicts with `ast.literal_eval` (not by
eye) to get an exact list of conflicts and dict1-only entries, rather than
transcribing 76 MAC prefixes by hand. Confirmed the `d8:3a:dd` conflict
against `api.macvendors.com` before picking a value. After merging,
imported the real module and confirmed all 7 previously-lost entries
resolve correctly, the `d8:3a:dd` conflict resolves to the verified
value, and `_nm_oui_vendor()` picks up the merged table. `grep -n
"^_NM_OUI = {"` confirms exactly one definition remains. `py_compile` and
`selftest.py` both clean — 35/35 on 3.11 and 3.12 under `xvfb-run`, zero
route changes (this table isn't part of any served page's byte-identical
content, only affects what name a MAC resolves to at runtime), so no
golden-file rebaseline was needed this time.

## Firewall rules — search bar + names

You asked for a search bar on the firewall rules list, and names shown
alongside the IP where available. Both are now on all three places that
list blocked hosts: the web overlay on `/3d`, the same overlay on
`/sankey`, and the desktop "Firewall rules" window (opened from the
Topology window's ⛔ FIREWALL button).

**Names — where they come from, in priority order:**

1. A label you've set for that IP in the device inventory (Quality →
   device list) — this is the same label already used everywhere else in
   the app, not a new naming system.
2. A known LAN vendor, from the OUI (vendor) prefix of its MAC address in
   your ARP cache — only applies to devices on your own network, which
   won't cover most firewall entries (those are usually internet IPs with
   no ARP entry).
3. A handful of well-known addresses (Google DNS, Cloudflare DNS, Quad9,
   OpenDNS, multicast/broadcast ranges) — instant, no lookup needed.
4. A reverse-DNS (PTR) lookup, simplified the same way the rest of the app
   already simplifies hostnames (`ec2-...compute-1.amazonaws.com` → `AWS`,
   `lclhrb-in-f138.1e100.net` → `Google`, etc. — reused the existing
   `_nm_friendly_host` machinery rather than inventing a second one).

If none of those find anything, the row just shows the IP with a blank
name — never the IP repeated as a fake "name". PTR lookups run in a
background thread and get cached; they never block the page or the
window from loading. A host with no PTR record at all resolves once,
caches "nothing found", and isn't retried every refresh — so a page full
of unnamed scanner IPs doesn't turn into a DNS-lookup storm every few
seconds.

**Search bar:** filters by IP or name (case-insensitive substring) across
the blocked-hosts table, the "other rules" list, and the "written in the
last 10 minutes" list. On the web pages it also shows "N of M shown" next
to the box. Filtering is instant and client-side — it re-filters data
already on the page rather than re-querying the firewall (which goes
through `netsh`/`nft` subprocess calls and would be far too slow to run
on every keystroke).

**One bug caught in testing:** my first version of the `/api/firewall`
change used `self._monitor` inside the request handler, which doesn't
exist there — the server object is called `server_self` in that closure
(a pattern already used elsewhere in the same handler, e.g. `_license_ok`).
That produced a raw HTTP 500 instead of the app's normal JSON error
response. Found by actually calling the endpoint rather than just reading
the code, fixed before shipping.

**Also noticed, not fixed (outside what was asked):** there are two
separate `_NM_OUI` vendor-lookup dictionaries in the file with different
contents — an earlier one (Philips Hue, VMware, Hyper-V, NVIDIA, Sonos,
more Microsoft prefixes) and a later one (Apple, Nest, a smaller
Google/Raspberry Pi set) that silently overwrites the first at startup
because they share the same name. Only the second one's entries are ever
actually used, anywhere in the app, including in this new feature. This
predates this session's changes. Say if you want it merged into one list.

**Verified (not assumed):**

- Called `_nm_fw_names()` directly against real IPs: `8.8.8.8`/`1.1.1.1`
  resolved instantly via the special-address fast path; a real
  reverse-DNS-only address (`208.67.220.220`) came back empty on the
  first call and resolved to `dns.umbrella.com` ~3 seconds later once the
  background lookup finished; an unroutable documentation address
  (`203.0.113.5`) stayed correctly absent rather than looping forever.
  Also confirmed the device-label path against a real temporary `SpeedDB`
  with a label set on an IP.
- Started the real `_ThreeDServer` and fetched `/api/firewall` for real —
  confirmed the 9 keys (was 8), reproduced and then fixed the
  `server_self` bug against the live endpoint, not just by reading the
  diff.
- Fetched the real `/3d` and `/sankey` HTML and confirmed the search box,
  match-count element, name column, and the new `fwRender()` function are
  present in the actual served page.
- Built the real desktop "Firewall rules" window under `xvfb-run` with a
  real `EtherApeWindow` and `Tk()` root, with fake blocked IPs and names
  fed in: confirmed the Treeview shows all 4 test rows correctly (IP,
  name, rule, state — unnamed IPs show `—`), typing "moscow" filtered to
  the one row whose *name* contains it (not just IP substring matching),
  typing an IP fragment filtered correctly, the "N of M shown" label
  updated live, and clearing the box restored all rows.
- `selftest.py`: 35/35 green on both Python 3.11 (static + every served
  route) and 3.12 under `xvfb-run`. `/3d`, `/sankey` and `/api/firewall`
  were the only things that changed (search UI + names column + the new
  API key) — re-baselined with `--update-ok` and confirmed clean
  immediately after. `/threats` and `/talkers` don't have a firewall
  overlay at all, so they were correctly untouched.

## Classic view removed

You said Modern is the way forward and Classic should come out, including
out of the guide. Done — Classic is gone, not just hidden behind a setting.

**What was deleted from `speedtest_monitor.py`** (1,551 lines net, verified
against a full pre-removal backup, not estimated):

- Module-level gauge-drawing helpers used only by Classic: `_hex_rgb`,
  `draw_gauge`, `_bg_image_path`, `draw_metal_bg`, `draw_view_dial`.
- `SpeedTestMonitor._load_view_data`, `_export_to`, `_style`, `_titl`,
  `_neon_bar`, `_neon_line` — all Classic-only rendering helpers.
- `SpeedTestMonitor.create_graph` — the entire Classic window builder.
- The Settings dialog's "Background Image" section and "Interface Style"
  (Classic/Modern radio button) section — there's only one UI now, so
  there's nothing left to pick between.
- `bg_image` / `ui_style` from the config defaults and the config-restore
  whitelist, and the two lines in Settings' save handler that wrote them.
- The `__main__` block's Classic-vs-Modern dispatch — replaced with a
  single unconditional `ModernWindow(monitor)`.
- Two now-dead leftovers found while sweeping for stragglers: the
  `DNS_COL` module constant and the `ModernWindow._cycle_matrix` stub
  (`pass  # Matrix rain lives in classic UI only`) — both had zero
  remaining callers, confirmed by grep before removal.

**What was deliberately left alone:** the module-level `_MODERN_MODE` flag
and the four call sites that branch on it (`_make_header` and three
others). ModernWindow is the only caller now, so that flag is always
`True` for the life of the window — but ripping out the conditional
would mean touching shared window-chrome rendering code for a
cosmetic-only cleanup with no user-visible effect. Fixed the one
docstring that was actively wrong ("Build a window header that adapts to
Classic vs Modern style") to explain the current, simpler reality instead.
Left `SpeedTestMonitor._fig = None` in place too — harmless, and removing
it buys nothing.

**Guide rewritten, not just trimmed** — the Dashboard, Gauges, Charts and
Colour Themes pages described Classic's rotary dial, background-image
picker and clickable gauge-row colour swatches, none of which exist
anymore. Rewrote all four from a direct read of `ModernWindow`'s actual
build methods (`_build_topbar`, `_build_sidebar`, `_build_gauges`,
`_build_viewbar`, `_build_charts`, `_update_charts`) rather than guessing
what changed:

- **Dashboard** — now describes the real layout: top bar (nav shortcuts,
  LIVE/TESTING/DNS CHECK badge, clock), the 17-button sidebar icon strip
  (with each button's actual label and target), the gauge strip, and the
  view bar (Today / This Week / This Month / All Time + day-by-day ◄ ►
  history navigation).
- **Gauges** — corrected from "270° neon speedometer with a needle" (that
  was Classic) to what Modern actually renders: a value card with a dot,
  big digital readout, unit, a proportional progress bar, and a 40-point
  sparkline, plus the separate "TODAY" stats card (Tests / DNS / Max DL /
  Jitter).
- **Charts** — corrected the 2×3 grid description to match what
  `_update_charts` actually draws: Download/Upload/Latency respecting the
  view-bar selection, a real-time psutil TX/RX traffic panel (not part of
  the recorded history), DNS history, and a text statistics table. Also
  removed the old "Daily Averages (14-day bar chart)" panel, which is not
  one of Modern's six panels.
- **Colour Themes** — removed the "click a swatch on the gauge row for a
  custom colour" instructions; Modern's gauge cards don't have per-channel
  colour pickers, only the five preset themes in Settings still apply.
- Also fixed four smaller stale references elsewhere in the guide that
  pointed at Classic-only UI text: "Click SETTINGS in the button bar" →
  "Click ⚙ PREFS in the sidebar", "Click ▶ RUN SPEED TEST NOW" / button
  relabeling to "◌ RUNNING…" → the sidebar RUN button + the LIVE badge's
  actual TESTING state, "Click the DNS button in the button bar" → the
  sidebar DNS button + DNS CHECK badge state, and the DNS per-host
  breakdown description (it was described as a live chart overlay, which
  was Classic-only — corrected to say it's recorded and shown in the
  generated report instead), plus one screenshot caption and one Agents
  how-to step that both still said "button bar".

**Verified (not assumed):**

- Full `py_compile`, then `pyflakes` for undefined names — 0 — after the
  bulk deletion and again after every follow-up edit.
- `grep -n "Classic\|ui_style\|bg_image"` across the whole file — zero
  hits, confirmed twice (once right after the deletion, once again at the
  end after the guide rewrite).
- `selftest.py` on Python 3.11 (static checks + all served routes/APIs)
  and on Python 3.12 under `xvfb-run` (real `Tk()` root, `ModernWindow`
  actually constructed, honeypot radar pane laid out): 35/35 green on
  both, 1 skip (desktop check skips on 3.11, which has no tkinter — that's
  the expected, existing split between the two interpreters, not new).
- Fetched the real `/guide` route from a running `_ThreeDServer` and read
  the actual rendered HTML back to confirm the new Dashboard/Gauges/
  Charts/Colours text is present, and that "Classic", "ui_style",
  "button bar" and the old "RUNNING…" button-label text are all gone from
  the served page.
- `/guide` was the only route that changed (65,549 → 64,995 bytes, purely
  from the rewritten sections) — re-baselined with `--update-ok` and
  confirmed clean against the new baseline immediately after. Every other
  route and API response byte-identical, so nothing else leaked from this
  change.
- Build ID bumped to `b-6446ed81` (sha256 of the file, first 8 hex chars)
  so the status bar shows whether a running instance includes this.

## Guide updated

Added everything above to the in-app guide (`? GUIDE` / `/guide`) — same
`UserGuideWindow.CONTENT` dict the rest of the guide is built from, no new
top-level sections (so no nav changes, no orphan risk):

- **Settings → Data** (new `h2` in the existing `'settings'` entry): what
  "Purge corrupt speed readings…" does, the three-step backup/count/purge
  sequence, and that it's safe to run any time.
- **Honeypot** (existing `'honeypot'` entry): new `h2` "Tarpit" — on by
  default, what it does, the 3-minute hold / 150-connection cap, that UDP
  is never tarpitted, the toggle, and an explicit line that this is *not*
  the ARP-spoofing LaBrea tarpit that was declined. Also updated the "Web
  view" bullets to explain "Stuck now" (instantaneous) vs "Held total"
  (cumulative) — the exact distinction that was behind your "Stuck now: 0"
  question — and fixed the "low-interaction... hangs up" line, which was no
  longer accurate now that tarpit-on is the default.
- **Reports & Scheduling** (existing `'report'` entry): added "honeypot
  activity" to the Contents bullet (it was already a report section but
  had never been listed there), and a new "Honeypot section" `h2`
  describing Attacker-Seconds Wasted and that the AI assessment gets the
  same figure.

**Verified:** started the real `_ThreeDServer`, fetched the actual `/guide`
route over HTTP, and read the rendered HTML back — confirmed all three
additions render in the right place, HTML-escaped correctly, with real
em-dashes/curly-quotes rather than literal `—`/`’` text.
`selftest.py` 36/36 green on both interpreters; `/guide` was the only route
that changed (62,711 → 65,549 bytes), re-baselined with `--update-ok`.

## "Stuck now" reads 0 with one honeypot entry — investigated, not a bug

You reported one honeypot entry but "Stuck now" showing 0. I can't see your
running instance from here, so I reproduced the shape of it with real
sockets rather than guessing. Two confirmed, non-buggy explanations, plus a
fix for the actual gap this exposed:

1. **"Stuck now" is instantaneous, not historical.** It's a live count of
   connections currently mid-tarpit, not "did this hit ever get tarpitted."
   A hit from even a few seconds ago, where the attacker has since
   disconnected (or the 180s hold simply finished), will correctly show 0
   forever after — the row stays in the hit table, but the tarpit already
   let go of that socket. That's very likely what you're seeing.
2. **If that entry is on a UDP port** (53 DNS, 123 NTP, 161 SNMP, 1900 SSDP,
   11211 memcached, 137 NetBIOS, 5353 mDNS, 389 CLDAP, 19 chargen, 111
   portmap) — it will *always* read 0. UDP decoys never tarpit, by the same
   never-reply rule that was already there (answering would make this
   machine an amplification reflector). Check the Port/proto column on that
   row.

I measured the mechanism directly to make sure: a real client that connects,
sends one byte, and disconnects immediately (i.e. a scanner that doesn't
linger) still gets held by the tarpit — confirmed `tarpit_seconds` ticks up
(2.9s in one measured run) even though "Stuck now" is back to 0 within a
few seconds because the attacker already left. The mechanism is working;
the instantaneous counter alone just can't tell you that after the fact.

**What I shipped because of this:** the web console now also shows **"Held
total (session)"** next to "Stuck now" — a running cumulative total of
seconds actually spent tarpitting (backed by the `tarpit_seconds` field
that was already there from the last build, just not surfaced on the live
page). That one answers "did it ever actually catch anything" even for
hit-and-run scanners where "Stuck now" only shows 1 for a moment. New
`fmtSecs()` helper formats it the same way as the report's `_fmt_secs`
(`Ns` / `Nm Ns` / `Nh Nm`).

**Still worth checking on your end**, since I can't see your live process:
the build ID in your status bar (should be `b-78978af4` after this update —
if it isn't, you're running a stale process and none of the above applies
yet), and whether the "Tarpit (stall connections)" checkbox is actually
ticked. If it *is* ticked, the entry is TCP, it's recent, and both "Stuck
now" and "Held total" read 0 — that's the case that would actually be a
bug, and I'd want to know that specifically.

## Attacker-seconds wasted — report + AI assessment

You asked for this specifically after the tarpit build. `_NMHoneypot.summary()`
already tracked `tarpit_seconds` (cumulative time held this session) — this
wires it into the two places that were still missing it:

- **Report** (`generate_report`, honeypot section): the stat row was
  `grid-2` (Connection Attempts, Unique Sources) — now `grid-3` with a third
  card, **Attacker-Seconds Wasted**, formatted as `Ns` / `Nm Ns` / `Nh Nm` by
  a small new `_fmt_secs()` helper local to that section. Also added to
  `report_data['honeypot']` (the JSON blob embedded in the report page) as
  `tarpit_seconds`, raw, for anything downstream that wants the number
  un-formatted.
- **AI assessment** (`_nm_honeypot_ai_prompt`): added a line — `Tarpit: on,
  3 connection(s) currently held, 137 attacker-second(s) wasted this
  session...` — so the model's summary can actually mention it instead of
  only ever describing hits/sources/services.

**Verified (not assumed):** built a real `SpeedTestMonitor` in a temp
working directory, a real `_NMHoneypot` with fabricated hits and
`_tarpit_seconds = 137.4`, called the real `generate_report()`, and read the
actual HTML file it wrote to disk — confirmed the `grid-3` card is present
in the honeypot section specifically (not just somewhere in the page),
showing the correctly-formatted `2m 17s`, and confirmed
`_nm_honeypot_ai_prompt()` produces `Tarpit: on, 3 connection(s)... 137
attacker-second(s)...` from that same summary. `selftest.py` stayed 36/36
green on both interpreters with no golden-file changes needed (report
generation isn't a hashed route, so this was expected, but checked rather
than assumed).

## Honeypot tarpit — stall connections, gobble attacker resources

**Scope confirmed with Trevor first**, because this is the exact phrase that
was declined last session as a LaBrea tarpit (ARP-spoofing IPs the host
doesn't own). What got built instead is different in kind, not just degree:
it only ever prolongs a connection a scanner *already made* to a port this
machine *already legitimately has bound* — no ARP, no claiming addresses
that aren't this host's, no new MITM/legal surface. Same 15 TCP decoy ports
as before (21,22,23,25,445,1433,2323,3306,3389,5432,5900,6379,8080,9200,
27017). UDP decoys are untouched — they still never reply (amplification
target risk still applies, and "stuck" doesn't mean anything for UDP).

**What changed, `_NMHoneypot` (speedtest_monitor.py):**

- Behavior before: accept, maybe send a banner, `recv()` up to 512 bytes
  with a 4s timeout, close. Fast, ~instant.
- Behavior now: same accept/banner/recv/record happens first — unchanged,
  so hit logging and sweep/alert detection still fire immediately, not
  delayed by however long the hold runs — then, if tarpit is on, the *same*
  connection is held open and drip-fed one byte at a time (`_tarpit()`)
  instead of closing. A blocked `recv()` on the attacker's end is a stuck
  thread/socket on THEIR side.
  - Hold: up to 180s per connection (`TARPIT_HOLD_SECONDS`).
  - Drip: one byte every 2–6s (`TARPIT_BYTE_DELAY`), small send/recv
    buffers, draining anything they send so their OS buffer doesn't back up
    and force an early disconnect.
  - Capped at 150 concurrently-held connections (`MAX_TARPIT_CONNS`) — this
    is the actual safety-relevant number, not the hold time: every held
    connection is one thread mostly asleep in `time.sleep()`, so even the
    cap is cheap, but an *uncapped* tarpit under a real flood is a
    self-inflicted thread/socket exhaustion risk on your own machine. Once
    the cap is hit, new connections fall back to the old fast-close instead
    of queueing or blocking anything else.
- New `SpeedTestMonitor`... no — new instance state: `_tarpit_enabled`,
  `_tarpit_active` (currently-held count), `_tarpit_seconds` (cumulative
  time held this session). Exposed in `summary()` / `/api/honeypot` as
  `tarpit_enabled`, `tarpit_active`, `tarpit_seconds`.

**Toggle, default ON:**

- Module-level `_NM_HP_TARPIT = {'on': True}`, same pattern as the existing
  auto-block flag — needed because `_NMHoneypot` is recreated fresh on every
  start, so this is what survives a stop/start.
- `POST /api/honeypot/control {action:'tarpit', on:bool}` — new control
  action, same dispatch as start/stop/test/block/autoblock/ai. This endpoint
  was already loopback-only for every action; nothing needed changing there.
- Web console (`/honeypot`): new "Tarpit (stall connections)" checkbox next
  to Auto-block, plus a "Stuck now" stat card (`tarpit_active`, refreshes
  every 3s like the rest of the page).
- Desktop Tk honeypot window (the fallback, still present): matching
  checkbox, and the status line now appends "· N stuck now" when anything's
  currently held.
- Both start paths (web control's `start` action and the Tk window's
  `start()`) now pass `tarpit=_NM_HP_TARPIT['on']` into the new instance, so
  the choice actually takes effect regardless of which surface starts it.

**Verified (not assumed):**

- Real sockets, not reasoning about the code: instantiated a real
  `_NMHoneypot` on a real loopback port, connected a real client socket, and
  measured the actual held-open time and byte-by-byte arrival — 3.47s held
  (with hold/delay constants compressed for a fast test — same code path,
  shorter numbers) vs. instant close with `tarpit=False`. Confirmed the hit
  is recorded within 0.5s of connecting, well before the hold ends — the
  tarpit doesn't delay detection.
- Cap enforcement measured directly: capped at 2 for the test, opened 4
  simultaneous connections, confirmed exactly 2 held and 2 fast-closed
  rather than all 4 queueing or blocking.
- UI: under `xvfb-run` with a real Tk root, opened the actual desktop
  honeypot window, found the real "Tarpit" checkbutton by walking the
  widget tree, confirmed it defaults checked, and confirmed clicking it
  actually flips the module-level toggle both directions.
- `selftest.py` on Python 3.11 (static + pyflakes) and 3.12 under
  `xvfb-run` (desktop construction + honeypot radar pane): 36/36 green.
  `/honeypot` and `/api/honeypot` were the only routes that changed
  (expected — new checkbox/card and three new JSON keys, no keys removed);
  re-baselined with `selftest.py --update-ok` and confirmed clean against
  the new baseline. Every other route byte-identical, so nothing else
  leaked.

**Not done / your call:**

- No UDP tarpitting — UDP is connectionless, and the "never reply" rule for
  those 10 ports stays for the amplification-target reason already in the
  handoff. Say if you want something different there (it'd have to be a
  different mechanism, not "hold the connection").
- Hold time (180s), byte delay (2–6s), and the concurrency cap (150) are my
  defaults, not something you specified a number for — easy to change if
  you want it more aggressive or more conservative.
- Didn't add tarpit stats to the honeypot section of the report generator
  or the AI analysis prompt — tell me if you want "N attacker-seconds
  wasted" showing up there too.

---

## Corrupt speed data purge (previous message, build `b-346cdf46`)

Settings → Data → "Purge corrupt speed readings…". Counts and nulls
out-of-range download/upload values (the old units-mismatch bug) directly
in `speedtest_data.db`, backing up the file first. Full detail was sent
with that build; not repeating it here.
