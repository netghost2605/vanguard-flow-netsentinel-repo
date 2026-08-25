#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Vanguard Flow NetSentinel - Linux launcher
#
#   ./run-linux.sh              start the app
#   ./run-linux.sh --check      report what is missing and exit
#   ./run-linux.sh --setup      create the venv and install everything
#
# Creates a private virtualenv in .venv so nothing touches the system Python
# (Debian/Ubuntu refuse system pip installs under PEP 668 anyway).
# ---------------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"
APP="speedtest_monitor.py"

c_ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
c_warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
c_bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; }
have()   { command -v "$1" >/dev/null 2>&1; }

# --- system packages -------------------------------------------------------
check_system() {
  local missing=()
  echo "System:"
  if python3 -c 'import tkinter' 2>/dev/null; then
    c_ok "python3-tk (the GUI toolkit)"
  else
    c_bad "python3-tk MISSING - the app cannot start without it"; missing+=("python3-tk")
  fi

  if have tshark; then
    c_ok "tshark $(tshark -v 2>/dev/null | head -1 | awk '{print $2}') - packet capture"
  else
    c_warn "tshark not found - live topology and capture views will be disabled"
    missing+=("tshark")
  fi

  if have nft; then c_ok "nftables - firewall blocking and kill switch"
  else c_warn "nft not found - blocking and the kill switch will be disabled"; missing+=("nftables"); fi

  if   have librespeed-cli; then c_ok "librespeed-cli (open source speed test)"
  elif have speedtest-cli;  then c_ok "speedtest-cli (open source speed test)"
  elif have speedtest;      then c_ok "speedtest (Ookla)"
  else
    c_warn "no speed-test CLI - speed tests will not run"
    missing+=("speedtest-cli")
  fi

  if have docker; then c_ok "docker - Pi-hole deployment available"
  else c_warn "docker not found - Pi-hole deployment unavailable"; fi

  if [ ${#missing[@]} -gt 0 ]; then
    echo
    echo "To install what is missing:"
    if   have apt-get; then echo "    sudo apt install ${missing[*]}"
    elif have dnf;     then echo "    sudo dnf install ${missing[*]}"
    elif have pacman;  then echo "    sudo pacman -S ${missing[*]}"
    else echo "    (install with your package manager): ${missing[*]}"; fi
  fi
}

# --- python environment ----------------------------------------------------
setup_venv() {
  if [ ! -x "$PY" ]; then
    echo "Creating virtualenv in $VENV ..."
    python3 -m venv --system-site-packages "$VENV" || {
      echo "Could not create the virtualenv. Install python3-venv:"
      echo "    sudo apt install python3-venv"; exit 1; }
  fi
  echo "Installing Python packages ..."
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet numpy matplotlib pillow psutil \
      || { echo "Package install failed."; exit 1; }
  # Optional: nicer chart tooltips and ML anomaly detection. Not fatal.
  "$PY" -m pip install --quiet mplcursors scikit-learn 2>/dev/null \
      && c_ok "optional extras installed" \
      || c_warn "optional extras skipped (mplcursors / scikit-learn)"
}

check_python() {
  echo
  echo "Python packages:"
  [ -x "$PY" ] || { c_bad "virtualenv not created - run: ./run-linux.sh --setup"; return; }
  for mod in numpy matplotlib PIL psutil; do
    if "$PY" -c "import $mod" 2>/dev/null; then c_ok "$mod"; else c_bad "$mod MISSING"; fi
  done
  for mod in mplcursors sklearn; do
    if "$PY" -c "import $mod" 2>/dev/null; then c_ok "$mod (optional)";
    else c_warn "$mod not installed (optional)"; fi
  done
}

case "${1:-run}" in
  --check) check_system; check_python ;;
  --setup) check_system; setup_venv; check_python
           echo; echo "Setup complete. Start it with:  ./run-linux.sh" ;;
  *)
    [ -x "$PY" ] || { echo "First run - setting up."; check_system; setup_venv; }
    # Capture and firewall need privileges. Rather than demanding sudo for the
    # whole GUI, tell the user how to grant just what is needed.
    if have tshark && ! groups | grep -qw wireshark; then
      c_warn "You are not in the 'wireshark' group, so capture may need sudo."
      echo "      sudo usermod -aG wireshark \$USER   # then log out and back in"
    fi
    exec "$PY" "$APP" "$@"
  ;;
esac
