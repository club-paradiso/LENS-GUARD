#!/bin/sh
# Capture this Mac's OWN traffic headers for a labeled LENS-GUARD experiment.
#
# Run it yourself from a terminal; LENS-GUARD never starts it:
#   sudo scripts/capture-own-host.sh --run --iface en0 --mac <this Mac's en0 MAC> \
#     --label video_call --seconds 120 --packets 100000
#
# Only frames to or from this Mac's own interface address are kept (BPF
# "ether host"). Each record keeps 14 bytes: the Ethernet header, so no IP
# address or payload is written. Output goes to the git-ignored captures/.
# Read docs/OWNED_DEVICE_PROTOCOL.ko.md first. Do not use on networks or
# devices you do not own or have explicit permission to test.
set -eu

MAX_SECONDS=600
MAX_PACKETS=200000
SNAPLEN=14
LABELS="video_call cloud_backup web_browsing media_streaming idle live_stream_upload other_non_camera"

usage() {
  echo "Usage: sudo $0 --run --iface IFACE --mac MAC --label LABEL [--seconds N<=$MAX_SECONDS] [--packets N<=$MAX_PACKETS]" >&2
  echo "Labels: $LABELS" >&2
  exit 2
}

run=0 iface="" mac="" label="" seconds=60 packets=50000
while [ $# -gt 0 ]; do
  case "$1" in
    --run) run=1 ;;
    --iface) iface="${2:-}"; shift ;;
    --mac) mac="$(printf '%s' "${2:-}" | tr 'A-F' 'a-f')"; shift ;;
    --label) label="${2:-}"; shift ;;
    --seconds) seconds="${2:-}"; shift ;;
    --packets) packets="${2:-}"; shift ;;
    *) usage ;;
  esac
  shift
done

printf '%s' "$iface" | grep -Eq '^[a-z]+[0-9]+$' || { echo "Invalid --iface." >&2; usage; }
printf '%s' "$mac" | grep -Eq '^([0-9a-f]{2}:){5}[0-9a-f]{2}$' || { echo "Invalid --mac." >&2; usage; }
case " $LABELS " in *" $label "*) ;; *) echo "Invalid --label. Camera labels need an owned camera; see the protocol." >&2; usage ;; esac
printf '%s' "$seconds" | grep -Eq '^[0-9]+$' && [ "$seconds" -ge 10 ] && [ "$seconds" -le "$MAX_SECONDS" ] || { echo "--seconds must be 10–$MAX_SECONDS." >&2; usage; }
printf '%s' "$packets" | grep -Eq '^[0-9]+$' && [ "$packets" -ge 100 ] && [ "$packets" -le "$MAX_PACKETS" ] || { echo "--packets must be 100–$MAX_PACKETS." >&2; usage; }

# The interface's own address must match, so the filter cannot target another device.
own="$(/sbin/ifconfig "$iface" 2>/dev/null | awk '/ether /{print tolower($2); exit}')"
if [ -z "$own" ] || [ "$own" != "$mac" ]; then
  echo "--mac does not match $iface's own address. Only this host's traffic may be captured." >&2
  exit 3
fi

root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/captures/$(date +%Y%m%d-%H%M%S)-$label.pcap"
filter="ether host $mac"
echo "Interface: $iface    Filter: $filter    Snap length: $SNAPLEN bytes"
echo "Limit: $seconds s or $packets frames, whichever comes first"
echo "Output: $out"

if [ "$run" -ne 1 ]; then
  echo "Dry run. Nothing was captured. Add --run and use sudo to capture."
  exit 0
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Packet capture needs administrator rights. Re-run with sudo yourself." >&2
  exit 4
fi
if [ ! -t 0 ]; then
  echo "Confirmation needs an interactive terminal." >&2
  exit 5
fi
printf 'This captures only %s traffic on %s, which you own. Type CAPTURE to continue: ' "$mac" "$iface"
read -r answer
[ "$answer" = "CAPTURE" ] || { echo "Cancelled. Nothing was captured."; exit 0; }

umask 077
mkdir -p "$root/captures"
/usr/sbin/tcpdump -i "$iface" -s "$SNAPLEN" -c "$packets" -w "$out" "$filter" &
pid=$!
( sleep "$seconds"; kill -INT "$pid" 2>/dev/null ) &
timer=$!
wait "$pid" || true
kill "$timer" 2>/dev/null || true
if [ -n "${SUDO_USER:-}" ] && [ -f "$out" ]; then
  chown "$SUDO_USER" "$out" "$root/captures"
fi
echo "Saved $out (git-ignored). Record its label in a manifest, analyze it, then delete it as the protocol describes."
