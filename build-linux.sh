#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build-linux.sh - package Vanguard Flow NetSentinel for Linux
#
#   ./build-linux.sh deb        build a .deb   (Debian / Ubuntu / Mint)
#   ./build-linux.sh appimage   build an AppImage (runs on any distro)
#   ./build-linux.sh all        build both
#
# Nothing licence-encumbered is bundled. tshark, nftables and the speed-test
# CLI are DECLARED as dependencies, never redistributed - which is what keeps
# the GPL and Ookla licence questions out of the package entirely.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

APP=netsentinel
NAME="Vanguard Flow NetSentinel"
VER="${VER:-1.0.0}"
ARCH=all
OUT=dist-linux
MAIN=speedtest_monitor.py

die()  { printf '\033[31mERROR\033[0m %s\n' "$1"; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }

[ -f "$MAIN" ] || die "$MAIN not found - run this from the project folder"

# ---------------------------------------------------------------------------
stage_tree() {
  local root="$1"
  rm -rf "$root"
  mkdir -p "$root/usr/lib/$APP" "$root/usr/bin" \
           "$root/usr/share/applications" \
           "$root/usr/share/icons/hicolor/256x256/apps" \
           "$root/usr/share/doc/$APP"

  cp "$MAIN" "$root/usr/lib/$APP/"
  [ -f nm_client.py ]        && cp nm_client.py        "$root/usr/lib/$APP/"
  [ -f speedtest_agent.py ]  && cp speedtest_agent.py  "$root/usr/lib/$APP/"
  [ -f LICENSE.txt ]         && cp LICENSE.txt         "$root/usr/share/doc/$APP/"
  [ -d web ]                 && cp -r web              "$root/usr/lib/$APP/"

  # launcher
  cat > "$root/usr/bin/$APP" <<EOF
#!/bin/sh
exec python3 /usr/lib/$APP/$MAIN "\$@"
EOF
  chmod 755 "$root/usr/bin/$APP"

  # desktop entry
  cat > "$root/usr/share/applications/$APP.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$NAME
GenericName=Network Monitor
Comment=Measure what your broadband actually delivers
Exec=$APP
Icon=$APP
Terminal=false
Categories=Network;Monitor;System;
Keywords=network;broadband;speedtest;monitor;capture;
EOF

  # icon: use the app's own if present, else draw a placeholder
  if [ -f icon.png ]; then
    cp icon.png "$root/usr/share/icons/hicolor/256x256/apps/$APP.png"
  else
    python3 - "$root/usr/share/icons/hicolor/256x256/apps/$APP.png" <<'PYEOF'
import sys
try:
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (256, 256), (4, 12, 24, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((28, 28, 228, 228), outline=(56, 184, 240, 255), width=6)
    pts = [(48, 168), (86, 120), (118, 146), (156, 74), (208, 110)]
    d.line(pts, fill=(56, 240, 168, 255), width=8, joint="curve")
    im.save(sys.argv[1])
except Exception:
    open(sys.argv[1], "wb").close()
PYEOF
  fi
}

# ---------------------------------------------------------------------------
build_deb() {
  command -v dpkg-deb >/dev/null || die "dpkg-deb not found (sudo apt install dpkg-dev)"
  info "Building .deb"
  local root="$OUT/deb"
  stage_tree "$root"
  mkdir -p "$root/DEBIAN"

  # Dependencies are DECLARED, not shipped. tshark stays GPL on the user's
  # system and we never redistribute it.
  cat > "$root/DEBIAN/control" <<EOF
Package: $APP
Version: $VER
Section: net
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.9), python3-tk, python3-numpy, python3-matplotlib,
 python3-pil, python3-psutil
Recommends: tshark, nftables, speedtest-cli
Suggests: docker.io, python3-sklearn
Maintainer: Vanguard Flow <support@example.com>
Description: $NAME
 Records what your broadband connection actually delivers and produces a
 timestamped evidence report suitable for a dispute with your provider.
 .
 Also provides live network topology from packet capture, per-host traffic
 analysis, geographic views, firewall blocking and remote site agents.
 .
 Packet capture requires tshark and membership of the wireshark group.
 Firewall features require nftables and root.
EOF

  cat > "$root/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ -x /usr/bin/update-desktop-database ]; then
    update-desktop-database -q /usr/share/applications || true
fi
echo "Vanguard Flow NetSentinel installed."
echo
echo "For packet capture, add yourself to the wireshark group:"
echo "    sudo usermod -aG wireshark \$USER    # then log out and back in"
echo
echo "For speed tests, install a CLI (open source options):"
echo "    sudo apt install speedtest-cli"
exit 0
EOF
  chmod 755 "$root/DEBIAN/postinst"

  dpkg-deb --build --root-owner-group "$root" "$OUT/${APP}_${VER}_${ARCH}.deb" >/dev/null
  ok "$OUT/${APP}_${VER}_${ARCH}.deb"
  dpkg-deb -I "$OUT/${APP}_${VER}_${ARCH}.deb" | sed 's/^/     /'
}

# ---------------------------------------------------------------------------
build_appimage() {
  info "Building AppImage"
  local root="$OUT/AppDir"
  stage_tree "$root"

  cp "$root/usr/share/applications/$APP.desktop" "$root/$APP.desktop"
  cp "$root/usr/share/icons/hicolor/256x256/apps/$APP.png" "$root/$APP.png" 2>/dev/null || true

  cat > "$root/AppRun" <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec python3 "\$HERE/usr/lib/$APP/$MAIN" "\$@"
EOF
  chmod 755 "$root/AppRun"

  if command -v appimagetool >/dev/null; then
    ARCH=x86_64 appimagetool "$root" "$OUT/${NAME// /_}-${VER}-x86_64.AppImage" >/dev/null 2>&1 \
      && ok "$OUT/${NAME// /_}-${VER}-x86_64.AppImage" \
      || die "appimagetool failed"
  else
    printf '  \033[33m!\033[0m appimagetool not installed - AppDir staged at %s\n' "$root"
    echo "     Get it from https://github.com/AppImage/AppImageKit/releases"
    echo "     then run:  appimagetool $root"
  fi
}

mkdir -p "$OUT"
case "${1:-all}" in
  deb)      build_deb ;;
  appimage) build_appimage ;;
  all)      build_deb; build_appimage ;;
  *)        die "usage: $0 [deb|appimage|all]" ;;
esac
info "Done. Output in $OUT/"
