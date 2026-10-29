#!/usr/bin/python3
"""AI-Assisted. Read-only, local evidence collection for a physical Linux live boot."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess


def text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, PermissionError):
        return None


def command(args):
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=10, check=False)
        return {"exit_code": result.returncode, "output": result.stdout.strip()[:12000],
                "error": result.stderr.strip()[:2000]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"unavailable": type(error).__name__}


def efi_byte(name):
    try:
        path = Path("/sys/firmware/efi/efivars") / (name + "-8be4df61-93ca-11d2-aa0d-00e098032b8c")
        data = path.read_bytes()
        return data[4] if len(data) == 5 else "unexpected-length"
    except OSError:
        return "unavailable"


def collect():
    devices = []
    for path in sorted(Path("/sys/bus/pci/devices").glob("*")):
        pci_class = text(path / "class") or ""
        if pci_class[2:4] not in ("01", "02", "03", "04", "0c"):
            continue
        driver = path / "driver"
        devices.append({"vendor": text(path / "vendor"), "device": text(path / "device"),
                        "class": pci_class, "driver": driver.resolve().name if driver.is_symlink() else None})
    virtualization = command(["systemd-detect-virt"])
    rootfs = command(["findmnt", "-n", "-o", "FSTYPE", "/"])
    live = Path("/run/live/medium").exists() or Path("/run/initramfs/live").exists()
    cmdline = text("/proc/cmdline") or ""
    module_versions = command(["dpkg-query", "-W", "-f=${Package} ${Version}\\n",
                               "dhampir-branding", "dhampiros-artwork", "dhampiros-motion", "linux-image-amd64"])
    return {
        "schema": 1, "collected_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Read-only local observations; no functional hardware certification",
        "manufacturer": text("/sys/class/dmi/id/sys_vendor"),
        "model": text("/sys/class/dmi/id/product_name"),
        "kernel": platform.release(), "architecture": platform.machine(),
        "virtualization": virtualization, "live_environment_detected": live,
        "root_filesystem_type": rootfs, "packages": module_versions,
        "secure_boot_variable": efi_byte("SecureBoot"), "setup_mode_variable": efi_byte("SetupMode"),
        "secure_boot_tool": command(["mokutil", "--sb-state"]),
        "kernel_lockdown": text("/sys/kernel/security/lockdown"),
        "tirdad_module_loaded": Path("/sys/module/tirdad").is_dir(),
        "kernel_flags_present": {flag: flag in cmdline.split() for flag in
                                 ("slab_nomerge", "init_on_alloc=1", "init_on_free=1", "module.sig_enforce=1")},
        "pci_devices": devices,
        "functional_checks": {name: "not-tested" for name in
                              ("display", "wifi", "audio", "touchpad", "suspend_resume", "battery", "installation")},
        "privacy": "No hostname, user name, serial, UUID, MAC, SSID, IP, EDID or disk contents collected. No upload performed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New local JSON file; existing files are never overwritten")
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("Run this read-only collector inside the Linux live session")
    report = collect()
    # Exclusive creation also rejects an existing symlink. No filesystem,
    # network, firmware, partition, package or authentication settings change.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(f"Saved local read-only observations to {args.output}")
    print("Functional checks remain not-tested until the hardware is actually exercised.")


if __name__ == "__main__":
    main()
