"""Read only L2 headers and lengths. Never interpret or return payload bytes."""

from collections import Counter
import io
import math
import re
import struct

from scapy.all import RadioTap, RawPcapReader
from .engine import MAX_PACKETS, Observation, analyze

MAX_BYTES = 32 * 1024 * 1024
SUPPORTED_LINKTYPES = {1, 105, 127}
MAC = re.compile(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\Z")


def validate_container(data):
    """Scapy tolerates some incomplete records; reject them before parsing."""
    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        endian = "<" if magic[0] in (0xd4, 0x4d) else ">"
        offset = 24
        while offset < len(data):
            if offset + 16 > len(data):
                raise ValueError("Truncated PCAP record header.")
            size = struct.unpack_from(endian + "I", data, offset + 8)[0]
            offset += 16 + size
            if offset > len(data):
                raise ValueError("Truncated PCAP packet data.")
    elif magic == b"\x0a\x0d\x0d\x0a":
        offset = 0
        endian = "<"
        while offset < len(data):
            if offset + 12 > len(data):
                raise ValueError("Truncated PCAPNG block.")
            if data[offset:offset+4] == magic:
                bom = data[offset+8:offset+12]
                if bom not in (b"\x4d\x3c\x2b\x1a", b"\x1a\x2b\x3c\x4d"):
                    raise ValueError("Invalid PCAPNG byte order.")
                endian = "<" if bom[0] == 0x4d else ">"
            size = struct.unpack_from(endian + "I", data, offset+4)[0]
            if size < 12 or size % 4 or offset + size > len(data):
                raise ValueError("Invalid PCAPNG block size.")
            if struct.unpack_from(endian + "I", data, offset+size-4)[0] != size:
                raise ValueError("PCAPNG block length mismatch.")
            kind = struct.unpack_from(endian + "I", data, offset)[0]
            if kind == 3:
                raise ValueError("PCAPNG packets without timestamps are unsupported.")
            if kind == 6:
                if size < 32:
                    raise ValueError("Truncated PCAPNG enhanced packet.")
                caplen = struct.unpack_from(endian + "I", data, offset+20)[0]
                if 32 + ((caplen + 3) & ~3) > size:
                    raise ValueError("Truncated PCAPNG packet data.")
            offset += size
    else:
        raise ValueError("Not a supported PCAP or PCAPNG file.")


def normalize_allowlist(values):
    result = {v.strip().lower() for v in values if v.strip()}
    if not result or len(result) > 64 or any(not MAC.fullmatch(v) for v in result):
        raise ValueError("Enter 1–64 authorized MAC addresses, separated by commas.")
    return result


def parse_capture(data, allowed):
    if len(data) > MAX_BYTES:
        raise ValueError("Maximum capture size is 32 MiB.")
    if len(data) < 24:
        raise ValueError("Not a complete PCAP/PCAPNG header.")
    validate_container(data)
    allowed = normalize_allowlist(allowed)
    counts = Counter()
    observations = []
    links = set()
    seen = set()
    try:
        with RawPcapReader(io.BytesIO(data)) as reader:
            default_link = getattr(reader, "linktype", None)
            if default_link is not None and default_link not in SUPPORTED_LINKTYPES:
                raise ValueError("Unsupported link type. Use Ethernet, 802.11 or Radiotap.")
            for raw, meta in reader:
                counts["records"] += 1
                if counts["records"] > MAX_PACKETS:
                    raise ValueError("Capture exceeds the 200,000 packet limit.")
                link = getattr(meta, "linktype", default_link)
                if link not in SUPPORTED_LINKTYPES:
                    raise ValueError("Unsupported link type. Use Ethernet, 802.11 or Radiotap.")
                links.add(link)
                if hasattr(meta, "sec"):
                    timestamp = meta.sec + meta.usec / (1e9 if reader.nano else 1e6)
                else:
                    timestamp = ((meta.tshigh << 32) | meta.tslow) / meta.tsresol
                if not math.isfinite(timestamp):
                    raise ValueError("Invalid capture timestamp.")
                wirelen = meta.wirelen
                if wirelen < len(raw) or wirelen > 262144:
                    raise ValueError("Invalid captured packet length.")
                rssi = None
                if link in (105, 127):
                    offset = 0
                    if link == 127:
                        if len(raw) < 8:
                            counts["malformed"] += 1
                            continue
                        offset = struct.unpack_from("<H", raw, 2)[0]
                        if offset < 8 or offset > len(raw):
                            counts["malformed"] += 1
                            continue
                        radio = RadioTap(raw[:offset])
                        value = getattr(radio, "dBm_AntSignal", None)
                        if value is not None and -127 <= value <= 0:
                            rssi = value
                    header = raw[offset:offset+24]
                    if len(header) < 24:
                        counts["malformed"] += 1
                        continue
                    frame, flags = header[0], header[1]
                    # Exclude AP downlink aggregation, WDS, control and null-data frames.
                    if frame & 3 or (frame >> 2) & 3 != 2 or frame >> 4 not in (0, 8) or flags & 3 != 1:
                        counts["not_station_uplink"] += 1
                        continue
                    source = header[10:16].hex(":")
                    if source not in allowed:
                        counts["outside_allowlist"] += 1
                        continue
                    # Retry frames are skipped, even when their original was not captured.
                    if flags & 8:
                        counts["retry_frames"] += 1
                        continue
                    key = (source, header[22:24], round(timestamp, 3))
                    if key in seen:
                        counts["duplicate_frames"] += 1
                        continue
                    seen.add(key)
                    wirelen = max(0, wirelen - offset)
                else:
                    if len(raw) < 14:
                        counts["malformed"] += 1
                        continue
                    source = raw[6:12].hex(":")
                    if source not in allowed:
                        counts["outside_allowlist"] += 1
                        continue
                observations.append(Observation(timestamp, source, wirelen, rssi))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Capture could not be decoded; check its format and integrity.") from exc
    counts["accepted"] = len(observations)
    return observations, {**dict(counts), "linktypes": sorted(links),
                          "visibility": "ethernet_source_only" if 1 in links else "wifi_station_uplink_only"}


def analyze_capture(data, allowed, declared_source="unverified_file"):
    if declared_source not in {"synthetic_file", "user_declared_authorized_capture", "unverified_file"}:
        raise ValueError("Invalid source declaration.")
    observations, diagnostics = parse_capture(data, allowed)
    result = analyze(observations, declared_source, diagnostics=diagnostics)
    if diagnostics["visibility"] == "ethernet_source_only":
        result["limitations"].append("Ethernet source MACs do not prove a Wi-Fi device or represent all nearby devices. Gateways may aggregate traffic.")
    if not observations:
        result["limitations"].append("No eligible packets matched the allowlist. This is not evidence of absence.")
    return result
