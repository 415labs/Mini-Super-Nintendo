#!/usr/bin/env bash
# One-step installer for the SNES GPIO pad daemon (Raspberry Pi 4).
#   bash install.sh              install for 2 pads
#   bash install.sh -n 1         install for 1 pad
#   bash install.sh -n 2 -r 4000 -t 3 -a 3    tuned for low latency (see docs/LATENCY.md)
#   bash install.sh --uninstall
set -euo pipefail
cd "$(dirname "$0")"

PADS=2; RATE=1000; HALF=6; CPU=""
UNINSTALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    -n) PADS="$2"; shift 2 ;;
    -r) RATE="$2"; shift 2 ;;
    -t) HALF="$2"; shift 2 ;;
    -a) CPU="$2"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (see bash install.sh --help)"; exit 1 ;;
  esac
done

SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

if [ "$UNINSTALL" -eq 1 ]; then
  $SUDO systemctl disable --now snes-pad 2>/dev/null || true
  $SUDO rm -f /etc/systemd/system/snes-pad.service /usr/local/bin/snes_pad /etc/modules-load.d/uinput.conf
  $SUDO systemctl daemon-reload
  echo "Uninstalled."
  exit 0
fi

if ! grep -q "Raspberry Pi 4\|Raspberry Pi 400\|Compute Module 4" /proc/device-tree/model 2>/dev/null; then
  echo "WARNING: this does not look like a Raspberry Pi 4. The daemon uses BCM2711 registers"
  echo "         and will NOT work on other models. Continue anyway? [y/N]"
  read -r a; [ "$a" = "y" ] || exit 1
fi
command -v gcc >/dev/null || { echo "gcc not found: sudo apt install build-essential"; exit 1; }

OPTS="-n $PADS -r $RATE -t $HALF"
[ -n "$CPU" ] && OPTS="$OPTS -a $CPU"

echo "==> Building"
gcc -O2 -Wall -Wextra -o snes_pad software/snes_pad.c

echo "==> Installing to /usr/local/bin"
$SUDO systemctl stop snes-pad 2>/dev/null || true
$SUDO install -m 755 snes_pad /usr/local/bin/snes_pad

echo "==> Enabling uinput (virtual gamepads)"
$SUDO modprobe uinput
echo uinput | $SUDO tee /etc/modules-load.d/uinput.conf >/dev/null

echo "==> Installing service ($OPTS)"
sed "s|@OPTIONS@|$OPTS|" software/snes-pad.service | $SUDO tee /etc/systemd/system/snes-pad.service >/dev/null
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now snes-pad
sleep 1

if systemctl is-active --quiet snes-pad; then
  echo
  echo "Done: snes-pad is running with: $OPTS"
  echo "Test the pads:   sudo python3 software/snes_test.py --evdev -n $PADS"
else
  echo
  echo "The service did not start. Details:"
  journalctl -u snes-pad -n 15 --no-pager || true
  exit 1
fi
