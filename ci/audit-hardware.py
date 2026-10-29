#!/usr/bin/python3
"""AI-Assisted. Match a sanitized PCI target to an image's offline driver inventory."""

import fnmatch
import json
from pathlib import Path
import subprocess
import sys

root, target_path, output = (Path(value).resolve() for value in sys.argv[1:4])
target = json.loads(target_path.read_text())
output.mkdir(parents=True, exist_ok=True)


def safe(path):
    # Follow no guest links while inspecting module metadata on the host.
    relative = path.relative_to(root)
    return all(not (root.joinpath(*relative.parts[:index])).is_symlink()
               for index in range(1, len(relative.parts) + 1))


versions = sorted((root / "usr/lib/modules").glob("*"))
if not versions:
    raise SystemExit("No kernel module inventory")
results = []
for version in versions:
    aliases_path = version / "modules.alias"
    if not safe(aliases_path) or not aliases_path.is_file():
        raise SystemExit("Unsafe or missing kernel alias metadata")
    aliases = [line.split()[1:3] for line in aliases_path.read_text().splitlines()
               if line.startswith("alias ")]
    devices = []
    for device in target["devices"]:
        drivers = sorted({driver for pattern, driver in aliases
                          if fnmatch.fnmatchcase(device["linux_modalias"].lower(), pattern.lower())})
        inventory = []
        for driver in drivers:
            modules = [p for p in version.rglob("*.ko*") if
                       p.name.split(".ko", 1)[0].replace("-", "_") == driver.replace("-", "_") and safe(p)]
            for module in modules:
                firmware = subprocess.check_output(["modinfo", "-F", "firmware", str(module)], text=True).splitlines()
                signer = subprocess.check_output(["modinfo", "-F", "signer", str(module)], text=True).strip()
                patterns = []
                for pattern in firmware:
                    # Firmware metadata is data, never a shell command or path to execute.
                    if ".." in Path(pattern).parts or Path(pattern).is_absolute():
                        raise SystemExit("Unsafe firmware metadata")
                    matches = []
                    for suffix in ("", ".xz", ".zst"):
                        matches.extend(str(p.relative_to(root / "usr/lib/firmware"))
                                       for p in (root / "usr/lib/firmware").glob(pattern + suffix)
                                       if p.resolve().is_relative_to(root) and p.is_file())
                    patterns.append({"pattern": pattern, "present_paths": sorted(set(matches))})
                inventory.append({"module": str(module.relative_to(root)), "signer": signer,
                                  "firmware_inventory": patterns})
        devices.append({**device, "matching_drivers": drivers, "module_inventory": inventory,
                        "status": "driver-alias-present" if drivers else "no-driver-alias-found"})
    results.append({"kernel": version.name, "devices": devices})
report = {
    "status": "offline-driver-inspection", "target": target["target"], "kernels": results,
    "physical_test": "not-performed", "scope": "PCI aliases and installed module/firmware metadata only",
    "limits": ["No assertion that a device initializes or works on real hardware",
               "Firmware alternatives listed by modinfo are not all required for this device",
               "Display, Wi-Fi, audio, touchpad, sleep, thermals and installation require a physical live boot"],
}
(output / "hardware-driver-report.json").write_text(json.dumps(report, indent=2) + "\n")
for kernel in results:
    for device in kernel["devices"]:
        print(f"{kernel['kernel']} {device['pci_id']}: {', '.join(device['matching_drivers']) or 'NO MATCH'}")
