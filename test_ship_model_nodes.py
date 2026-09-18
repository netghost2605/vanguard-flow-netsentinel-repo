#!/usr/bin/env python3
"""
Verifies the 3D topology view's real ship-model (glb.glb) feature, across
its three iterations this session:

  1. Real ship-model meshes were added as a per-node substitute (small
     captures only), via a hand-written GLB parser/template builder.
  2. That per-node substitution was tuned to a top-N-by-traffic ranking,
     then -- after Trevor saw it live and reported it hid the flag/colour
     "orb" identity on exactly his busiest, most-important hosts -- REVERTED
     entirely. Node meshes are now ALWAYS the plain flag sphere; the real
     ship model is never a node substitute again.
  3. The real ship model instead powers an ambient "flyby": a transient
     background pass using the real GLB template, triggered by host
     discovery, with the same fly-in/fly-out motion the old (removed)
     low-poly `_mkCruiser` ambient system used to have -- reusing the
     `_ships`/`_shipSpawn`/`_shipsUpdate` infrastructure that also drives
     the separate, intentionally-kept raider/block-kill dramatization.

There's no headless Three.js scene graph to inspect (see
test_3d_floor_removed.py for the same approach), so this checks the actual
served /3d HTML plus the server-side plumbing for the concrete, checkable
facts of the final state:

  1. A hand-written GLB parser/template builder exists (_NC_* functions) --
     deliberately NOT the stock three.js GLTFLoader addon, since that
     couldn't be reliably fetched in this app's sandboxed build/dev
     environment. It's scoped to exactly this file's verified asset shape:
     single scene, plain TRS transforms, no skinning/animation/morph
     targets, non-interleaved float32 position/normal/uv, uint32 indices,
     standard pbrMetallicRoughness materials.
  2. The `_NC_` prefix was chosen deliberately to avoid collision with the
     pre-existing, unrelated `_ship*`/`_shipHosts` naval-patrol-boat
     visualization already in this codebase -- neither identifier family
     leaks into the other.
  3. Node meshes are ALWAYS the plain flag sphere now (`useCraft=false`,
     hardcoded, never derived from node count or traffic rank). The
     craft-mode plumbing on `_getNodeMesh`/`_craftPool`/pooling/recursive
     raycasting is left in place (inert but harmless) rather than ripped
     out, since it's no longer reachable from rebuildGeometry but ripping
     it out would be a bigger, riskier change than the actual ask.
  4. `_getNodeMesh`/`_returnNodeMeshes` still pool ship-model clones
     separately from sphere meshes (_craftPool vs _meshPool) and tag them
     via `userData._kind` so the two pools never mix, even though nothing
     currently drives useCraft=true for a node.
  5. Raycasting is still recursive at BOTH hover and click sites (harmless
     with useCraft permanently false for nodes, but also needed for the
     flyby ships, which are also groups with no geometry of their own).
  6. `userData.nodeIdx` is still propagated onto every descendant mesh of a
     ship clone via `.traverse()` for when useCraft is ever true again.
  7. A studio environment map (PMREMGenerator-based) is present -- needed by
     MeshStandardMaterial on the real model (node craft path, dormant; and
     the flyby ships, active) or it renders almost black.
  8. Textures get anisotropic filtering -- its absence was the concrete,
     named root cause of Trevor's "quality looks shit" feedback on the
     first real-model pass.
  9. Server-side: /api/shipmodel is wired into the request dispatcher and
     served by a dedicated method that locates the bundled asset via the
     same generic _nm_resource_path() finder every other bundled resource
     uses (never a hardcoded path), and degrades to a graceful 404 rather
     than raising if the asset is missing/unreadable -- matching this
     app's established "never break the page" philosophy for optional
     assets (see _serve_vendor).
 10. The client's loader treats a failed fetch/parse as "stay on sphere
     nodes" (never lets the real-model feature take down the whole view).
 11. speedtest_monitor.spec and installer.nsi both bundle glb.glb following
     the exact existing bg.jpg pattern (datas.append / File /nonfatal),
     with a warning message if it's missing at build time, and the
     installer's uninstall section removes it again.
 12. The ambient real-ship flyby: `_mkFlyby()` clones `_NC_TEMPLATE` (never
     a low-poly placeholder, and never spawns at all if the template hasn't
     loaded yet); `_shipSpawn()` builds via `_mkFlyby()` for any non-raider
     kind; `_shipsScanHosts()` is called once per poll() tick, primes its
     seen-hosts set on the first tick (no flock on load), and spawns one
     flyby per genuinely-new host after that -- reusing the same
     `_ships`/`_shipsUpdate` array, throttle and off-screen-removal the
     raider dramatization already had, so a flyby flies in from one side,
     drifts across, and exits, exactly like the old (still-removed)
     `_mkCruiser` did.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "speedtest_monitor.py")
SPEC = os.path.join(HERE, "speedtest_monitor.spec")
NSI = os.path.join(HERE, "installer.nsi")


def main():
    src = open(TARGET, encoding='utf-8').read()

    # Isolate the /3d view's own inline script the same way
    # test_3d_floor_removed.py does, so matches can't accidentally come from
    # an unrelated view (e.g. the separate Top-Talkers 3D script).
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

    # ── GLB parser / template builder ───────────────────────────────────
    for fn in ('_NC_parseGLB', '_NC_accessorArray', '_NC_loadTexture', '_NC_buildTemplate', '_NC_startLoad'):
        check(f'function {fn}(' in view, f"hand-written GLB helper {fn}() is present")
    check('new THREE.GLTFLoader(' not in view and 'GLTFLoader.js' not in view,
          "the stock three.js GLTFLoader addon is NOT actually used at "
          "runtime (deliberately -- couldn't be reliably fetched in this "
          "sandboxed build environment; it may still be named in an "
          "explanatory code comment describing that decision)")

    # ── Naming collision avoidance ───────────────────────────────────────
    check('_craftPool' in view, "_craftPool (not _shipPool) is used for the ship-model pool")
    check('_shipPool' not in view,
          "the ship-model pool was NOT named _shipPool (would collide in "
          "spirit with the pre-existing, unrelated _ship*/_mkRaider naval "
          "combat-dramatization system already in this codebase)")

    # ── Old low-poly ambient cruiser: stays removed ──────────────────────
    # Checked against the FULL source, not just `view` -- gone from the
    # codebase entirely, not just from the narrower slice. A stale prose
    # comment mentioning the old name is fine; only the actual
    # construction/call is checked.
    check('function _mkCruiser(' not in src and '_mkCruiser()' not in src,
          "the old low-poly patrol-cruiser ship builder stays gone entirely "
          "(construction and call site both -- a comment may still name "
          "it) -- the flyby reuses the real ship model instead, not this")

    # These function definitions and the animate-loop call site live past
    # the _build3DTalkers boundary (the `view` slice stops there to dodge
    # that separate script's own shadowing `grid` variable -- see
    # test_3d_floor_removed.py), so check them against the full source.
    check('function _mkRaider(' in src and 'function _mkFlyby(' in src
          and 'function _shipKill(' in src and 'function _shipSpawn(' in src
          and 'function _shipsUpdate(' in src and 'function _shipsScanHosts(' in src,
          "all six ship-system functions are present: the kept raider "
          "dramatization (_mkRaider), the new real-ship flyby (_mkFlyby), "
          "and the shared spawn/kill/update/trigger plumbing")
    check("_shipSpawn('raider', e.ip);" in view,
          "a real block event still spawns a raider (via _realBlockEvents)")
    check("try{ _shipsUpdate(0.016); }catch(e){}" in src,
          "the animate loop still drives ship warp-in/kill/debris/drift "
          "updates for BOTH raiders and flybys (shared code path)")
    check("try{ _shipsScanHosts(d); }catch(se){}" in src,
          "poll() calls _shipsScanHosts() once per tick, so newly "
          "discovered hosts can trigger a flyby")

    # ── Node meshes: always plain spheres, never a substitute ───────────
    # The two earlier LOD schemes (all-or-nothing node-count gate, then
    # top-N-by-traffic ranking) are both gone -- Trevor's real complaint
    # once he saw either live was that a ship replacing a node hid the
    # flag/colour "orb" identity he relies on, worst on exactly the
    # busiest/most-labelled hosts he cares about most. `useCraft` is now a
    # hardcoded false at the one call site that matters (rebuildGeometry),
    # not derived from node count or traffic rank at all.
    check('N<=_NC_MAX_SHIP_NODES' not in view.replace(' ', ''),
          "the old all-or-nothing 'whole view under N nodes' gate is gone")
    check('craftIdx' not in view,
          "the top-N-by-traffic per-node craft-eligibility set (craftIdx) "
          "is gone -- that scheme was reverted too, not just the original "
          "all-or-nothing gate")
    check('ranked.sort((a,b)=>(nodes[b].frac||0)-(nodes[a].frac||0));' not in view,
          "the traffic-rank sort used by the reverted top-N scheme is gone")
    check('constuseCraft=false;' in view.replace(' ', ''),
          "rebuildGeometry hardcodes useCraft=false for every node -- "
          "nodes are always the plain flag sphere, unconditionally")
    check('const mesh=_getNodeMesh(r, nd.cc, col, nd.blocked, nd.local, useCraft);' in view,
          "each node still calls _getNodeMesh() with the (now-always-false) "
          "useCraft flag, rather than a separate craft-only code path "
          "being spliced in")

    # ── Pooling: craft vs sphere never mix (infra kept, even though it's ─
    #    currently dormant for node meshes -- see check block above) ─────
    check("function _getNodeMesh(r, cc, col, isBlocked, isLocal, useCraft){" in view,
          "_getNodeMesh() still accepts the useCraft flag")
    check('obj = _NC_TEMPLATE.clone();' in view,
          "_getNodeMesh()'s craft branch still clones the loaded template "
          "for new craft-mode pool instances (dormant for nodes, but left "
          "in place rather than ripped out)")
    check("obj.userData._kind = 'craft';" in view,
          "craft-mode pool objects are tagged userData._kind='craft'")
    check("mesh.userData._kind = 'sphere';" in view,
          "sphere pool objects are tagged userData._kind='sphere'")
    check("if(m.userData && m.userData._kind === 'craft') _craftPool.push(m);" in view,
          "_returnNodeMeshes() routes craft-kind objects back to _craftPool")
    check("else _meshPool.push(m);" in view,
          "_returnNodeMeshes() routes everything else back to _meshPool "
          "(the two pools never mix)")

    # ── Raycasting stays recursive ────────────────────────────────────────
    recursive_hits = view.count('raycaster.intersectObjects(_rayTargets,true)')
    check(recursive_hits == 2,
          "both hover and click sites call intersectObjects(_rayTargets,true) "
          "(recursive) -- found %d occurrence(s)" % recursive_hits)
    check('raycaster.intersectObjects(_rayTargets,false)' not in view,
          "no non-recursive intersectObjects(_rayTargets,false) call remains "
          "-- a THREE.Group has no geometry of its own, so a non-recursive "
          "raycast would silently find zero hits against a ship clone")

    # ── nodeIdx propagation onto ship clone descendants ─────────────────
    check('mesh.traverse(o=>{ o.userData.nodeIdx=i; });' in view,
          "userData.nodeIdx is propagated onto every descendant mesh of a "
          "ship clone via .traverse(), so a recursive raycast hit on any "
          "child resolves to the right node")

    # ── Studio env map (needed for MeshStandardMaterial PBR) ────────────
    check('PMREMGenerator' in view, "a PMREMGenerator-based studio env map was added")
    check('scene.environment=' in view.replace(' ', ''),
          "scene.environment is set from the generated env map")
    check('EquirectangularReflectionMapping' in view,
          "the env map canvas texture uses EquirectangularReflectionMapping")

    # ── Anisotropic filtering (root cause of "quality looks shit") ──────
    check('tx.anisotropy=renderer.capabilities.getMaxAnisotropy();' in view.replace(' ', ''),
          "loaded ship-model textures get anisotropic filtering -- the "
          "named root cause of the first-pass blurry/soft texture feedback")

    # ── Graceful degradation ─────────────────────────────────────────────
    check(".catch(err=>{" in view.replace(' ', '') and "_NC_TEMPLATE" in view,
          "the loader has a .catch() so a failed fetch/parse leaves "
          "_NC_TEMPLATE null and every node quietly stays a sphere, rather "
          "than breaking the view")

    # ── Ambient real-ship flyby ──────────────────────────────────────────
    check('let _ships=[], _shipLast=0, _shipHosts=new Set(), _shipPrimed=false;' in src,
          "the host-discovery tracking state (_shipHosts/_shipPrimed) is "
          "back, alongside the shared _ships array -- this time for the "
          "real-ship flyby, not the removed low-poly cruiser")
    check('function _mkFlyby(){' in src,
          "_mkFlyby() -- the real-ship-model flyby builder -- is defined")
    mkflyby_start = src.index('function _mkFlyby(){')
    mkflyby_end = src.index('function _shipSpawn(kind,label){')
    mkflyby_body = src[mkflyby_start:mkflyby_end]
    check('if(!_NC_TEMPLATE) return null;' in mkflyby_body,
          "_mkFlyby() returns null (no placeholder mesh) if the real "
          "template hasn't finished loading yet")
    check('obj = _NC_TEMPLATE.clone();' in mkflyby_body,
          "_mkFlyby() clones the real GLB template, not a low-poly mesh")
    check("obj.userData.kind='flyby';" in mkflyby_body,
          "flyby ship objects are tagged kind='flyby'")

    shipspawn_start = src.index('function _shipSpawn(kind,label){')
    shipspawn_end = src.index('function _shipsScanHosts(d){')
    shipspawn_body = src[shipspawn_start:shipspawn_end]
    check("if(kind!=='raider' && !_NC_TEMPLATE) return;" in shipspawn_body,
          "_shipSpawn() bails out BEFORE consuming its spawn-rate throttle "
          "when a non-raider (flyby) spawn is requested but the real "
          "template isn't loaded yet")
    check("obj = (kind==='raider') ? _mkRaider() : _mkFlyby();" in shipspawn_body,
          "_shipSpawn() builds a raider via _mkRaider() and everything "
          "else (i.e. a flyby) via _mkFlyby()")
    check('if(!obj) return;' in shipspawn_body,
          "_shipSpawn() bails out cleanly if the builder returned nothing "
          "(covers _mkFlyby()'s null-if-not-loaded-yet case)")
    check("vx: side*(kind==='raider'?3.4:2.1)" in shipspawn_body.replace(' ', '')
          or "vx: side*(kind==='raider'?3.4:2.1)," in shipspawn_body,
          "a flyby drifts at the slower non-raider speed (2.1) the shared "
          "motion code already had a branch for")

    check('function _shipsScanHosts(d){' in src,
          "_shipsScanHosts() -- the host-discovery trigger for the flyby "
          "-- is defined")
    scan_start = src.index('function _shipsScanHosts(d){')
    scan_end = src.index('function _shipKill(sh){')
    scan_body = src[scan_start:scan_end]
    check('if(!_shipPrimed){' in scan_body and 'hosts.forEach(h=>_shipHosts.add(h));' in scan_body,
          "the first poll tick primes _shipHosts with every host already "
          "in the capture, WITHOUT spawning -- so resuming on a busy real "
          "network doesn't spawn a flock of 'new' hosts at once")
    check("_shipSpawn('flyby', h);" in scan_body,
          "a genuinely new host (not seen this session) spawns a flyby")

    # Off-screen removal (the fly-in/drift/exit motion itself) is generic,
    # shared code -- not flyby-specific -- so just confirm it's still
    # intact and unconditional on ship kind.
    check('if(Math.abs(sh.obj.position.x)>52){' in src,
          "ships (raiders AND flybys alike) are removed once they drift "
          "past the same off-screen x boundary the old cruiser used")

    # ── Server-side route ────────────────────────────────────────────────
    check("def _serve_shipmodel(self, handler):" in src,
          "_serve_shipmodel() server method is defined")
    check("elif path == '/api/shipmodel':" in src,
          "/api/shipmodel is wired into the request dispatcher")
    check("server_self._serve_shipmodel(self)" in src,
          "the dispatcher entry actually calls _serve_shipmodel()")
    check("_nm_resource_path('glb.glb')" in src,
          "the bundled asset is located via the same generic "
          "_nm_resource_path() finder every other bundled resource uses "
          "(never a hardcoded path)")
    # The method must degrade gracefully (404 JSON), never raise past its
    # own boundary, on any failure to find/read the asset.
    shipmodel_start = src.index("def _serve_shipmodel(self, handler):")
    shipmodel_end = src.index("def _serve_flag(self, handler, cc):")
    shipmodel_body = src[shipmodel_start:shipmodel_end]
    check(shipmodel_body.count("handler._json(404,") >= 1,
          "_serve_shipmodel() returns a graceful 404 JSON error rather than "
          "raising when the asset is missing/unreadable/empty")
    check("handler._send(200, 'model/gltf-binary', data)" in shipmodel_body,
          "a found asset is served with the correct model/gltf-binary content type")

    # ── Build-time bundling (spec + installer) ──────────────────────────
    spec_src = open(SPEC, encoding='utf-8').read()
    check("ship_glb = HERE / 'glb.glb'" in spec_src,
          "speedtest_monitor.spec locates glb.glb next to the other bundled assets")
    check("datas.append((str(ship_glb), '.'))" in spec_src,
          "speedtest_monitor.spec bundles glb.glb via the same datas.append "
          "pattern used for bg.jpg")
    check("glb.glb not found in the build folder" in spec_src,
          "a clear build-time warning fires if glb.glb is missing (matching "
          "the bg.jpg warning's tone/format)")

    nsi_src = open(NSI, encoding='utf-8').read()
    check('File /nonfatal "glb.glb"' in nsi_src,
          "installer.nsi bundles glb.glb with File /nonfatal (a build run "
          "without it still produces a working installer)")
    check('Delete "$INSTDIR\\glb.glb"' in nsi_src,
          "installer.nsi's uninstall section removes glb.glb again")

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s))")
        sys.exit(1)
    print("RESULT: PASS -- real ship-model GLB wired in end-to-end: parser, "
          "pooling/raycasting infra (dormant for nodes, always spheres now), "
          "studio env map, anisotropic filtering, graceful degradation, "
          "server route, build-time bundling, AND the ambient real-ship "
          "flyby (host-discovery trigger, fly-in/fly-out motion shared "
          "with the raider dramatization, real GLB model, no placeholder "
          "fallback).")


if __name__ == "__main__":
    main()
