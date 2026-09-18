#!/usr/bin/env python3
"""
Verifies the 3D topology view change: "remove all the spaceships but dont
touch anything else."

This is the fourth and final chapter of the real-ship-model feature this
session (see CHANGES_this_session.md for the full history: per-node
substitution, reverted to top-N-by-traffic, reverted again to an ambient
flyby) -- Trevor's call this time was to pull the whole thing, not tune it
again. That means THREE separate things all had to come out together,
since each only existed to serve the others:

  1. The ships themselves: the raider that warps in and explodes on a real
     firewall block, and the flyby that crossed the background on a newly
     discovered host. Both spawned through the same `_ships` array/
     `_shipSpawn`/`_shipKill`/`_shipsUpdate` machinery.
  2. The real ship-model GLB pipeline (`_NC_*`): the hand-written parser,
     the fetch of `/api/shipmodel`, the studio environment map that existed
     solely so that model's PBR material wouldn't render black. Nothing
     else in the page ever consumed any of this.
  3. The per-node "craft" substitution path in `_getNodeMesh`/
     `_returnNodeMeshes` (`_craftPool`, `useCraft`) -- already permanently
     disabled (nodes were hardcoded to always render as spheres after an
     earlier revert this session), but the plumbing was still there. With
     the GLB pipeline gone, there's nothing left for it to ever draw from,
     so it comes out too rather than staying as dead weight.

What must NOT have moved: the real firewall-block detonation itself (the
radar boom + `_attackKills` counter + sonar ping) is a different feature
that merely USED to also spawn a raider as a side effect -- it stays, minus
only the ship-spawning lines. The host-discovery machinery for
`_shipsScanHosts` is gone entirely rather than left orphaned. Every other
part of the /3d view (walls, floor removal, sky, starfield, radar, protocol
bars, world view, talkers, everything not spaceship-shaped) is untouched by
this change, and this test does not re-verify any of it -- see
test_3d_floor_removed.py and test_sky_dither.py for those.

There's no headless Three.js scene graph to inspect, so this checks the
actual served /3d HTML plus the server-side plumbing for the concrete,
checkable fact that all three layers are gone, and that what's left behind
still makes sense on its own (no dangling references, no orphaned dead
code, the block-event detonation logic that isn't ship-related survives
intact).
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

    # ── 1. The ships themselves: gone, construction AND call sites ──────
    # Checked against the FULL source (not just `view`) since some of this
    # lived past the _build3DTalkers boundary that bounds `view`.
    for fn in ('_mkRaider', '_mkFlyby', '_shipSpawn', '_shipKill',
               '_shipsUpdate', '_shipsScanHosts', '_mkCruiser'):
        check(f'function {fn}(' not in src and f'{fn}(' not in src,
              f"{fn}() -- construction and every call site -- is gone entirely")
    for ident in ('_ships', '_shipLast', '_shipHosts', '_shipPrimed', 'SHIP_MAX'):
        check(ident not in src, f"{ident} state is gone, not just the functions that used it")
    check("try{ _shipsUpdate(0.016); }catch(e){}" not in src,
          "the animate loop no longer drives any ship update")
    check("try{ _shipsScanHosts(d); }catch(se){}" not in src,
          "poll() no longer scans for newly-discovered hosts to spawn a ship")

    # ── What must survive: the real block-event detonation, minus only the
    #    ship-spawning side effect it used to trigger ──────────────────────
    be_start = src.index("function _realBlockEvents(d){")
    be_end = src.index("\n}", be_start)
    block_events_body = src[be_start:be_end]
    check("_attackBooms.push(" in block_events_body,
          "a real block event still detonates a radar boom (unrelated to ships, untouched)")
    check("_attackKills++;" in block_events_body,
          "a real block event still increments the kill counter (untouched)")
    check("_sonarPing(false);" in block_events_body,
          "a real block event still triggers the sonar ping (untouched)")
    check("_shipSpawn(" not in block_events_body and "_shipKill(" not in block_events_body,
          "the block-event handler no longer spawns or kills a raider ship "
          "-- everything else about it is untouched")

    # ── 2. The real ship-model GLB pipeline: gone entirely ───────────────
    for ident in ('_NC_TEMPLATE', '_NC_LOAD_STARTED', '_NC_MAX_SHIP_NODES',
                  '_NC_COMPONENT_CTORS', '_NC_TYPE_SIZES', '_NC_parseGLB',
                  '_NC_accessorArray', '_NC_loadTexture', '_NC_buildTemplate',
                  '_NC_startLoad'):
        check(ident not in src, f"{ident} (real ship-model GLB pipeline) is gone")
    check('PMREMGenerator' not in view and 'scene.environment' not in view.replace(' ', ''),
          "the studio environment map (added solely for the ship model's PBR "
          "material) is gone -- the sphere nodes never needed it")
    check('EquirectangularReflectionMapping' not in view,
          "the env-map canvas texture setup is gone with it")

    # ── 3. The per-node craft-substitution plumbing: gone, not just dormant
    check('_craftPool' not in view, "the ship-model pool (_craftPool) is gone")
    check('useCraft' not in view, "the useCraft flag/parameter is gone from _getNodeMesh and its call site")
    check("function _getNodeMesh(r, cc, col, isBlocked, isLocal){" in view,
          "_getNodeMesh() no longer takes a useCraft parameter")
    check('const mesh=_getNodeMesh(r, nd.cc, col, nd.blocked, nd.local);' in view,
          "rebuildGeometry's call site no longer passes a useCraft argument")
    check("obj.userData._kind = 'craft';" not in view and "mesh.userData._kind = 'sphere';" not in view,
          "the now-pointless craft/sphere pool tagging is gone (only one "
          "pool exists now, so nothing needs to distinguish them)")
    rnm_start = view.index("function _returnNodeMeshes(){")
    rnm_end = view.index("\n}", rnm_start)
    return_body = view[rnm_start:rnm_end]
    check("_meshPool.push(m);" in return_body and "_craftPool" not in return_body,
          "_returnNodeMeshes() unconditionally returns every mesh to the "
          "single remaining pool")

    # ── Node meshes: still always plain flag spheres (this was already true
    #    before this change -- confirming it's still true, not re-litigating it)
    check("const geo = new THREE.SphereGeometry(1, 24, 16);" in view,
          "node meshes are still built from plain sphere geometry")
    check("const mat = new THREE.MeshPhongMaterial({shininess:180});" in view,
          "node meshes still use the original Phong material (not the "
          "removed ship model's Standard/PBR material)")

    # ── Raycasting / nodeIdx: the recursive call and .traverse() plumbing
    #    that existed to reach into a ship Group's child meshes are no
    #    longer NEEDED (nodes are plain, childless Mesh objects again), but
    #    intersectObjects(...,true) and a direct nodeIdx assignment are
    #    harmless on a childless mesh either way, so this only confirms the
    #    ship-specific .traverse() call -- the part that actually assumed a
    #    multi-mesh Group existed -- is gone, without demanding an unrelated
    #    revert of the raycast recursion flag that isn't broken.
    check('mesh.traverse(o=>{ o.userData.nodeIdx=i; });' not in view,
          "the ship-Group-specific nodeIdx-propagation-via-traverse() call "
          "is gone (nodes are plain meshes again, so a direct assignment is "
          "all that's needed -- and is still present just above)")
    check('mesh.userData.nodeIdx=i;' in view,
          "each node mesh still gets its nodeIdx set directly")

    # ── Server-side: /api/shipmodel route and its handler are gone ──────
    check("def _serve_shipmodel(self, handler):" not in src,
          "_serve_shipmodel() server method is gone")
    check("elif path == '/api/shipmodel':" not in src and "server_self._serve_shipmodel(self)" not in src,
          "/api/shipmodel is unwired from the request dispatcher")

    # ── Build-time bundling (spec + installer): glb.glb no longer shipped
    spec_src = open(SPEC, encoding='utf-8').read()
    check("ship_glb" not in spec_src and "glb.glb" not in spec_src,
          "speedtest_monitor.spec no longer bundles glb.glb -- the asset "
          "would just be dead weight in every install now")

    nsi_src = open(NSI, encoding='utf-8').read()
    check('File /nonfatal "glb.glb"' not in nsi_src,
          "installer.nsi no longer installs glb.glb")
    check('Delete "$INSTDIR\\glb.glb"' not in nsi_src,
          "installer.nsi's uninstall section no longer references glb.glb "
          "(nothing left to clean up post-install)")

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s))")
        sys.exit(1)
    print("RESULT: PASS -- every spaceship (raider, flyby) and the entire "
          "real ship-model GLB pipeline that fed them (parser, server "
          "route, build-time bundling, per-node craft-substitution "
          "plumbing, studio env map) are gone. The real block-event "
          "detonation (radar boom, kill counter, sonar ping) survives "
          "intact, minus only the ship-spawning side effect it used to "
          "trigger. Node meshes are unchanged plain flag spheres.")


if __name__ == "__main__":
    main()
