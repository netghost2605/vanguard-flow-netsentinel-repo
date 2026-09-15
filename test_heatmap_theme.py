#!/usr/bin/env python3
"""
Exercises the REAL _nm_open_heatmap() (no reimplementation, no mocked
rendering) against a real temp SQLite DB with real inserted readings, under
two different THEMES presets, and confirms:

  1. It doesn't crash under either theme (real Tk mainloop -- needs a
     display, run under xvfb).
  2. The rendered heatmap's colormap top (the "good" end) actually matches
     that theme's own accent colour for the selected metric -- not a fixed
     'viridis'/'magma_r' preset untouched by theme choice.
  3. Switching the fake monitor's theme and calling the exposed
     win._nm_rerender() (the same hook _apply_gauge_colors uses when you
     hit Save in Settings) changes the rendered colours in place, proving
     the "still open while you change theme" path works too, not just
     "colours are right the moment it's first opened".

Run under xvfb: xvfb-run -a python3.12 test_heatmap_theme.py
"""
import datetime
import importlib.util
import os
import sys
import tempfile

TARGET = "/tmp/work/extracted/speedtest_monitor.py"

spec = importlib.util.spec_from_file_location("stm_under_test", TARGET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_db_with_data(path):
    db = mod.SpeedDB(path)
    now = datetime.datetime.now()
    for i in range(20):
        ts = (now - datetime.timedelta(hours=i * 3)).isoformat()
        db.insert_reading(ts, download=200.0 + i, upload=30.0 + i, ping=15.0 + (i % 5))
    return db


class FakeMonitor:
    """Minimal stand-in exposing exactly what _nm_open_heatmap touches:
    ._db and .colors -- both read fresh on every _render() call, same as
    the real SpeedTestMonitor."""
    def __init__(self, db, theme_name):
        self._db = db
        self.theme_name = theme_name

    @property
    def colors(self):
        return mod.THEMES[self.theme_name]


def close_enough(rgba, hexcolor, tol=2):
    """matplotlib's to_rgba() round-trip on a hex string vs. a colormap's
    sampled RGBA can differ by float rounding; compare as 0-255 ints."""
    from matplotlib.colors import to_rgba
    a = tuple(round(v * 255) for v in rgba[:3])
    b = tuple(round(v * 255) for v in to_rgba(hexcolor)[:3])
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def main():
    import tkinter as tk

    tmpdir = tempfile.mkdtemp()
    db = make_db_with_data(os.path.join(tmpdir, "test.db"))

    root = tk.Tk()
    root.withdraw()

    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)
            print(f"FAIL: {msg}")
        else:
            print(f"ok:   {msg}")

    # ── 1. Open under Ocean, confirm colormap top == Ocean's download accent
    mon = FakeMonitor(db, "Ocean")
    win = mod._nm_open_heatmap(mon)
    root.update()

    check(hasattr(win, "_nm_rerender"), "win._nm_rerender exposed")
    check(hasattr(win, "_nm_fig"), "win._nm_fig exposed")

    ax = win._nm_fig.axes[0]
    im = ax.images[0]
    top_rgba = im.cmap(1.0)     # download is higher_better -> value 1.0 = the accent end
    check(close_enough(top_rgba, mod.THEMES["Ocean"]["download"]),
          f"Ocean theme: heatmap colormap top matches Ocean's download accent "
          f"({mod.THEMES['Ocean']['download']}), got {top_rgba}")

    # ── 2. Switch theme, call the SAME rerender hook _apply_gauge_colors
    #        uses, confirm the colormap actually changed to match.
    mon.theme_name = "Sunset"
    win._nm_rerender()
    root.update()

    ax2 = win._nm_fig.axes[0]
    im2 = ax2.images[0]
    top_rgba2 = im2.cmap(1.0)
    check(close_enough(top_rgba2, mod.THEMES["Sunset"]["download"]),
          f"After switching to Sunset + rerender: colormap top matches "
          f"Sunset's download accent ({mod.THEMES['Sunset']['download']}), "
          f"got {top_rgba2}")
    check(not close_enough(top_rgba2, mod.THEMES["Ocean"]["download"]),
          "Colormap top is no longer Ocean's colour after the theme switch "
          "(proves it actually re-derived the ramp, not just redrew stale one)")

    # ── 3. Ping is lower-is-better -- confirm the ramp direction is inverted
    #        (low value = accent, matching the old magma_r inversion this
    #        replaces) rather than blindly reusing the download direction.
    #        The theme-switch checks above already exercise the real
    #        end-to-end object for 'download'; this adds the ping-inversion
    #        case as a focused check on the exact function _render() calls
    #        for every metric, _nm_heatmap_cmap().
    cmap_ping = mod._nm_heatmap_cmap(mod.THEMES["Sunset"], "ping", higher_better=False)
    good_end = cmap_ping(0.0)   # low normalized value = low ping = good
    bad_end  = cmap_ping(1.0)   # high normalized value = high ping = bad
    check(close_enough(good_end, mod.THEMES["Sunset"]["ping"]),
          f"ping colormap: LOW value (good) end matches ping's accent "
          f"({mod.THEMES['Sunset']['ping']}), got {good_end}")
    check(close_enough(bad_end, mod.THEMES["Sunset"]["panel"]),
          f"ping colormap: HIGH value (bad) end fades to the panel tone "
          f"({mod.THEMES['Sunset']['panel']}), got {bad_end}")

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s) failed)")
        sys.exit(1)
    else:
        print("RESULT: PASS -- heatmap colours genuinely track the active theme, "
              "confirmed via the real _nm_open_heatmap()/_nm_heatmap_cmap(), "
              "not a reimplementation.")


if __name__ == "__main__":
    main()
