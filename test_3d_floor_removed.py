#!/usr/bin/env python3
"""
Verifies the 3D topology view change: "get rid of the floor and make the
space background a deep black so the stars stand out more."

There's no headless Three.js scene graph to inspect, so this checks the
actual served /3d HTML (the same bytes selftest.py's golden-file check now
covers) for the concrete, checkable facts of the change:

  1. The floor GridHelper and its solid PlaneGeometry fill mesh are both
     gone from the script -- not just hidden, actually removed from the
     scene-construction code.
  2. `grid` (the removed floor variable) is no longer referenced anywhere
     in the /3d script -- toggleGrid() no longer touches `grid.visible`,
     which would have thrown a ReferenceError on the very first click.
  3. `_wallGrids` (the 4 wall grids, deliberately left alone since Trevor
     only asked to remove the floor) is still built and still driven by
     toggleGrid() -- proving the walls survived the edit intact.
  4. The fog tint and both renderer.setClearColor() calls are all
     near-black (luminance below a tight threshold), not the old navy/cyan
     palette. There is no textured sky-gradient sphere any more at all --
     that mesh (SKY_TOP/MID/LOW/GLOW, a canvas gradient, then a dithering
     pass added on top of it) went through two rounds of real, shipped
     bugs in a row (8-bit banding, then a worse aliasing pattern from
     dithering an unmipmapped minified texture) and was removed outright
     rather than patched a third time -- a flat clear colour cannot band
     or alias because there is no texture and no gradient left to do
     either. This test locks that in: if SKY_TOP or a sky CanvasTexture
     ever reappears here, something regressed back toward the removed
     approach.
  5. The GRID button's tooltip no longer claims to control "the floor."
"""
import os
import re
import sys

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speedtest_monitor.py")


def _hex_luma(hexstr):
    """0-255 perceptual-ish luma from a '#rrggbb' or '0xrrggbb' string."""
    h = hexstr.lower().lstrip('#').replace('0x', '')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def main():
    src = open(TARGET, encoding='utf-8').read()

    # Isolate the /3d view's own inline script (bounded by its known
    # neighbours) so matches can't accidentally come from an unrelated
    # view (e.g. the separate Top-Talkers 3D script, which has its own
    # local `grid` variable and is untouched by this change).
    start = src.index("const canvas=document.getElementById('c');")
    end = src.index("function _build3DTalkers()")
    view = src[start:end]

    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)
            print(f"FAIL: {msg}")
        else:
            print(f"ok:   {msg}")

    check('new THREE.GridHelper(60,60' not in view,
          "floor GridHelper(60,60,...) construction is gone from the "
          "/3d script (stale prose comments mentioning the old floor "
          "convention are fine; only the actual construction call matters)")
    check('matches the near-black floor' not in view
          and 'matches the base floor colour' not in view.replace(
              'matches the near-black floor colour (see the floor fill above)', ''),
          "the solid floor-fill PlaneGeometry mesh's identifying comment is gone")
    check('PlaneGeometry(60,60)' not in view,
          "the floor's solid PlaneGeometry(60,60) fill mesh is gone "
          "(the wall panes use PlaneGeometry(W,D) with variables, not "
          "this literal pair)")

    # No bare `grid.` left anywhere in the view's script (the wall grids
    # are always addressed through _wallGrids / a local loop variable `g`,
    # never a bare identifier named exactly `grid`).
    bare_grid_refs = re.findall(r'(?<![\w.])grid\.', view)
    check(not bare_grid_refs,
          "no leftover bare `grid.` reference in the /3d script "
          "(would have been a ReferenceError once the floor grid was "
          "removed) -- found: %r" % bare_grid_refs)

    check('const _wallGrids=[];' in view, "_wallGrids array still declared")
    check('_wallGrids.push(g);' in view.replace(' ', '')
          or '_wallGrids.push(g)' in view,
          "wall grids are still being built and pushed into _wallGrids")
    check('_wallGrids.forEach(g=>{ g.visible=_gridVisible; });' in view,
          "toggleGrid() still drives the wall grids' visibility")
    check('grid.visible=_gridVisible;' not in view,
          "toggleGrid() no longer references the removed floor `grid` variable")

    # The textured sky-gradient sphere is gone entirely, not just
    # recoloured -- two different real bugs (8-bit banding, then a worse
    # aliasing pattern from dithering it) came out of that one texture, so
    # the fix was to remove the whole approach rather than patch it again.
    check('SKY_TOP' not in view and 'SKY_MID' not in view
          and 'SKY_LOW' not in view and 'SKY_GLOW' not in view,
          "sky gradient stop constants (SKY_TOP/MID/LOW/GLOW) are gone -- "
          "no gradient left to band or alias")
    check('_buildSky' not in view,
          "the sky-sphere-building function is gone entirely")
    check('cv.width=8; cv.height=512;' not in view,
          "the sky's specific 8x512 gradient canvas is gone (other, "
          "unrelated gradients elsewhere in the /3d script -- link "
          "colours, sparkle textures -- are fine and untouched)")
    check('SphereGeometry(900' not in view,
          "the 900-unit backdrop sphere mesh is gone -- the scene now "
          "relies solely on the renderer's flat clear colour for its "
          "background, which cannot band or alias")

    fm = re.search(r"const FOG_TINT=(0x[0-9a-fA-F]{6});", view)
    check(fm is not None, "FOG_TINT constant found")
    if fm:
        check(_hex_luma(fm.group(1)) <= 16,
              "FOG_TINT is near-black: %s" % fm.group(1))

    clears = re.findall(r"renderer\.setClearColor\((0x[0-9a-fA-F]{6}),1\);", view)
    check(len(clears) == 2, "found exactly 2 setClearColor() calls, got %d" % len(clears))
    check(all(_hex_luma(c) <= 16 for c in clears),
          "both setClearColor() values are near-black: %s" % clears)
    check(len(set(clears)) == 1,
          "both setClearColor() calls now agree on the same value "
          "(previously two different navy tones): %s" % clears)

    # The GRID button itself is page HTML, not part of the /3d script body,
    # so check it against the full source rather than the `view` slice.
    check('title="Show/hide the wall reference grid"' in src,
          "GRID button tooltip updated to no longer mention the floor")
    check('title="Show/hide the floor and wall reference grid"' not in src,
          "GRID button's old floor-mentioning tooltip text is gone")

    # The 4 glass wall panes (explicitly meant to survive this change,
    # since Trevor only asked to remove the floor) are still present.
    check('glassPane(' in view, "the 4 glass wall panes are still present")

    # Follow-up fix: Trevor reported the walls read as a visibly different,
    # lighter/bluer black than the (now-empty) floor space, plus a moire
    # effect off the wall grid lines -- both traced to the walls still being
    # pinned to the OLD floor's colour (0x070f1c) instead of the new
    # deep-black backdrop. Confirm the walls now derive their colour from
    # the same FOG_TINT constant the backdrop uses (an exact match, not a
    # close guess) and that the old floor-coloured literal is gone.
    check('GLASS_COLOR=FOG_TINT' in view,
          "wall glass colour now references the SAME constant as the "
          "backdrop's fog tint, guaranteeing an exact match rather than a "
          "hand-copied hex value that can drift out of sync again")
    check('GLASS_COLOR=0x070f1c' not in view,
          "the old floor-coloured literal is no longer assigned to "
          "GLASS_COLOR (it may still appear in an explanatory code comment "
          "describing the fix -- that's fine, only the live assignment "
          "matters)")
    wg = re.search(r"const W=60,D=60,G=(0x[0-9a-fA-F]{6}),G2=(0x[0-9a-fA-F]{6});", view)
    check(wg is not None, "wall grid line colour constants found")
    if wg:
        g_luma, g2_luma = _hex_luma(wg.group(1)), _hex_luma(wg.group(2))
        check(g_luma <= 8 and g2_luma <= 8,
              "wall grid lines are darkened to match the new deep-black "
              "family (luma<=8, tighter than the sky/fog floor of 16 since "
              "these sit on top of the glass rather than being the "
              "backdrop itself): G=%s (%.1f) G2=%s (%.1f)"
              % (wg.group(1), g_luma, wg.group(2), g2_luma))

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s))")
        sys.exit(1)
    print("RESULT: PASS -- floor (grid + fill mesh) fully removed, no "
          "dangling references, background/fog/clear-colour all deep "
          "black, walls left intact, button tooltip updated.")


if __name__ == "__main__":
    main()
