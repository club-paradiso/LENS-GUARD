"""Read-only capability inventory. No interface changes or capture commands."""

from pathlib import Path
import platform
import shutil


def capabilities():
    return {"os": platform.system(), "os_version": platform.mac_ver()[0],
            "architecture": platform.machine(), "tcpdump_installed": bool(shutil.which("tcpdump") or Path("/usr/sbin/tcpdump").exists()),
            "wireless_diagnostics_installed": Path("/System/Library/CoreServices/Applications/Wireless Diagnostics.app").exists(),
            "monitor_capture_verified": False, "capture_running": False,
            "next_step": "Read docs/MACOS.md. Validate collection locally only with an explicit authorized device scope. No capture is started by this command."}
