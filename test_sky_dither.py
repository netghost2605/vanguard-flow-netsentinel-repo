#!/usr/bin/env python3
"""
Verifies the 3D view's backdrop is now a genuinely flat, artifact-proof
colour, by actually rendering it with real Three.js in a real headless
browser and reading back the pixels -- not by reasoning about the code.

History, so the next person editing this file understands why it looks
like this: the 3D view's backdrop used to be a large inverted sphere
carrying a canvas-gradient texture. Two rounds of real, shipped bugs came
out of that ONE texture in a row:
  1. Once the gradient was squeezed into a "deep black" range (all stops
     within ~12 8-bit levels of #000), most of its 512 rows rounded to
     the same integer colour and stepped in hard rings every 15-25 rows --
     banding, visible as concentric rings on the 900-unit sphere.
  2. Dithering that gradient (the textbook fix for banding, and it did
     measurably shrink the identical-row runs in a real-browser test) made
     it WORSE on Trevor's machine: the texture is only 8x512 with
     minFilter:LinearFilter and no mipmaps, so under minification onto the
     900-unit sphere the high-frequency dither noise had nothing to
     pre-filter it and aliased into a fresh, uglier pattern.

The actual fix (this test locks it in) was to stop patching that texture
and remove it: no gradient, no canvas, no sphere -- just the renderer's
own flat clear colour as the backdrop, plus FogExp2 (computed live by the
shader per-pixel, never sampled from a texture, so it was never part of
either bug). A flat clear colour cannot band -- there's no gradient to
round -- and cannot alias -- there's no texture to minify.

This test renders TWO real WebGL scenes with the real three.min.js the app
ships (`/root/.nm_vendor/three.min.js`, referenced from speedtest_monitor.py
itself) in real headless Chromium:
  A. The CURRENT backdrop code, extracted verbatim from the file (just
     scene.fog + renderer.setClearColor, no sky mesh).
  B. A reconstruction of the OLD, removed sky-sphere-plus-gradient
     approach, as a negative control -- proving this test methodology can
     actually detect the bug it's checking for, not just trivially pass
     because nothing was drawn.
Then it reads back the rendered canvas pixels and checks that (A) is
PERFECTLY uniform -- literally every pixel byte-identical, the strongest
possible statement that there is no banding or aliasing left -- while (B)
is NOT uniform, confirming the control actually exercises the bug.
"""
import os
import re
import sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "speedtest_monitor.py")
# The app caches its own three.min.js to ~/.nm_vendor the first time the /3d
# view is opened (see the '/vendor/three.min.js' route in speedtest_monitor.py) --
# reuse that real copy rather than bundling a second one just for this test.
THREE_JS = os.path.join(os.path.expanduser("~"), ".nm_vendor", "three.min.js")

PAGE_TEMPLATE = """<!doctype html><html><body>
<canvas id="c" width="400" height="300"></canvas>
<script src="file://%(three_js)s"></script>
<script>
window.__renderResult = (() => {
  const canvas=document.getElementById('c');
  const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});
  renderer.setPixelRatio(1);
  renderer.setSize(400,300,false);
  %(backdrop_code)s
  const camera=new THREE.PerspectiveCamera(55, 400/300, 0.1, 2000);
  camera.position.set(0,6,22);
  camera.lookAt(0,0,0);
  renderer.render(scene,camera);
  return true;
})();
</script>
</body></html>"""

OLD_BUGGY_BACKDROP = """
const scene=new THREE.Scene();
const SKY_TOP='#000000', SKY_MID='#010104', SKY_LOW='#020207', SKY_GLOW='#04040c';
const FOG_TINT=0x010103;
scene.fog=new THREE.FogExp2(FOG_TINT,0.0125);
renderer.setClearColor(0x000000,1);
(function(){
  const cv=document.createElement('canvas'); cv.width=8; cv.height=512;
  const g=cv.getContext('2d');
  const grd=g.createLinearGradient(0,0,0,512);
  grd.addColorStop(0.00, SKY_TOP);
  grd.addColorStop(0.42, SKY_MID);
  grd.addColorStop(0.78, SKY_LOW);
  grd.addColorStop(0.93, SKY_GLOW);
  grd.addColorStop(1.00, SKY_MID);
  g.fillStyle=grd; g.fillRect(0,0,8,512);
  const tex=new THREE.CanvasTexture(cv);
  tex.magFilter=THREE.LinearFilter; tex.minFilter=THREE.LinearFilter;
  const sky=new THREE.Mesh(
    new THREE.SphereGeometry(900,32,24),
    new THREE.MeshBasicMaterial({map:tex,side:THREE.BackSide,
                                 depthWrite:false,fog:false}));
  sky.renderOrder=-1;
  sky.frustumCulled=false;
  scene.add(sky);
})();
"""


def extract_block(src, start_marker, end_marker):
    i = src.index(start_marker)
    j = src.index(end_marker, i)
    return src[i:j]


def render_and_read(page, backdrop_code, out_png):
    html = PAGE_TEMPLATE % {'three_js': THREE_JS, 'backdrop_code': backdrop_code}
    page_path = os.path.join(HERE, '_sky_flat_tmp.html')
    open(page_path, 'w').write(html)
    page.goto('file://' + page_path)
    page.wait_for_function("window.__renderResult === true", timeout=5000)
    page.locator('#c').screenshot(path=out_png)
    os.remove(page_path)


def main():
    src = open(TARGET, encoding='utf-8').read()

    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg); print(f"FAIL: {msg}")
        else:
            print(f"ok:   {msg}")

    if not os.path.exists(THREE_JS):
        print(f"FAIL: no cached three.min.js at {THREE_JS} yet -- open the "
              "3D view once in the app (it downloads and caches it on "
              "first use) and re-run this test")
        sys.exit(1)

    # Pull the CURRENT backdrop code straight out of the shipped file, so
    # this test can't drift from what's actually deployed.
    current_backdrop = extract_block(
        src,
        "const FOG_TINT=0x010103;",
        "/* ── Star sprite textures")
    check('new THREE.Mesh' not in current_backdrop
          and 'CanvasTexture' not in current_backdrop,
          "the extracted current backdrop code contains no mesh/texture "
          "construction at all (confirms the sky sphere is really gone, "
          "not just made invisible)")
    current_code = "const scene=new THREE.Scene();\n" + current_backdrop

    from PIL import Image

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=['--use-gl=swiftshader', '--enable-unsafe-swiftshader'])
        except Exception:
            browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
                                         args=['--use-gl=swiftshader', '--enable-unsafe-swiftshader'])
        page = browser.new_page()

        current_png = os.path.join(HERE, '_sky_current.png')
        old_png = os.path.join(HERE, '_sky_old_buggy.png')
        render_and_read(page, current_code, current_png)
        render_and_read(page, OLD_BUGGY_BACKDROP, old_png)
        browser.close()

    def pixel_variance(png_path):
        im = Image.open(png_path).convert('RGB')
        colors = im.getcolors(maxcolors=400 * 300)
        return colors

    current_colors = pixel_variance(current_png)
    old_colors = pixel_variance(old_png)

    check(current_colors is not None and len(current_colors) == 1,
          "CURRENT backdrop renders as PERFECTLY uniform colour -- every "
          f"single pixel identical (found {len(current_colors) if current_colors else 'too many (>120000)'} "
          "distinct colour(s)) -- there is nothing left in this scene that "
          "can band or alias")

    check(old_colors is None or len(old_colors) > 1,
          "negative control: the OLD sky-sphere-plus-gradient code (as "
          "removed) actually DOES render with more than one distinct "
          f"colour ({'>120000' if old_colors is None else len(old_colors)} "
          "found) -- confirms this test can tell the two approaches apart, "
          "it's not trivially passing")

    for p_ in (current_png, old_png):
        try:
            os.remove(p_)
        except OSError:
            pass

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s))")
        sys.exit(1)
    print("RESULT: PASS -- the current /3d backdrop, rendered for real with "
          "the app's own three.min.js in a real browser, comes out as a "
          "single uniform colour with zero variance. There is no gradient, "
          "no texture and no sphere left to band or alias, unlike the old "
          "removed approach (confirmed distinct in the same test).")


if __name__ == "__main__":
    main()
