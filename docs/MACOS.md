# macOS collection boundary

The application does not start packet capture. `lens-guard capabilities` only reports local OS/tool availability.

Observed locally on 2026-10-27: macOS 15.6.1, arm64. `/usr/sbin/tcpdump -D` listed en0 as wireless and associated. Wireless Diagnostics was installed. `/usr/sbin/tcpdump -i en0 -L` returned `Permission denied` while opening `/dev/bpf0`; therefore supported capture link types and monitor-mode delivery were not verified. No elevation was requested and no live capture was taken. See `hardware-check.json`.

[Apple's Wi-Fi trace guide](https://developer.apple.com/documentation/network/recording-a-wi-fi-packet-trace) distinguishes ordinary host traffic from low-level Wi-Fi frames and documents Wireless Diagnostics → Window → Sniffer. It also notes that normal Wi-Fi connectivity is unavailable during low-level capture. The guide's decryption-oriented advice about disabling passwords is **not needed for this project**: keep encryption enabled; only frame metadata is used.

## Local validation, only after a concrete authorization scope exists

1. Identify the owned/approved AP, transmitting devices, MAC addresses, channel, place and short test window. Permission for a venue does not authorize unrelated nearby devices.
2. Inspect capture permissions and monitor-mode support locally. Administrator permission, driver availability, channel and OS version may prevent capture. Do not infer support from the presence of en0 or Wireless Diagnostics.
3. Prefer an already available authorized, source-filtered PCAP. A managed-mode host capture may only show the Mac's own traffic; do not interpret it as a survey of the room.
4. If a controlled radio test is later authorized, use an isolated test environment and a capture filter restricted to the approved transmitting MAC. Verify that the platform really applies the filter. Bound time, bytes and packet count; keep only the header snap length needed for metadata. The capture tool is deliberately not automated here.
5. Wireless Diagnostics can collect an entire channel and may lack a per-device capture filter. Do not use it around unapproved networks merely because the analysis allowlist will discard them later. If collection cannot be restricted to the authorized scope, stop and use synthetic/offline data.
6. Import only approved data, label its origin, and check accepted counts, link type, duration and RSSI availability. Test a known active camera, a quiet camera, a video call, a backup, and ordinary traffic. Keep independent ground truth outside the packet stream.
7. Remove the raw capture according to the agreed retention period. Never add it to GitHub. Store only the minimized report when sufficient.

## Own-host capture for labeled confounders

`scripts/capture-own-host.sh` records only this Mac's own frames (`ether host` with the interface's own MAC, 14-byte snap length, time and packet limits) for non-camera labels. The user runs it with sudo and a typed confirmation; nothing in LENS-GUARD calls it. It has not been run during development. See [OWNED_DEVICE_PROTOCOL.ko.md](OWNED_DEVICE_PROTOCOL.ko.md).

## Not implemented or not verified

Live capture, channel hopping, background monitoring, driver modification, CSI extraction, direction finding, camera localization, silent-device discovery and any operational safety verdict. Apple documentation establishes an available procedure, not that this exact hardware/OS combination successfully delivered usable frames during this session.
