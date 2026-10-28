#!/usr/bin/python3
"""AI-Assisted. Inspect images read-only on a disposable runner with no secrets."""

import json
import os
from pathlib import Path
import subprocess

target = os.environ["IMAGE_TARGET"]
extension = {"iso": "iso", "virtualbox": "ova"}[target]
image = next(Path("candidate").glob(f"*.{extension}")).resolve()
scratch = Path("image-audit-work").resolve()
scratch.mkdir()
root = scratch / "rootfs"
report = Path("verification").resolve()


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


mounted = False
try:
    if target == "iso":
        squash = scratch / "filesystem.squashfs"
        run("xorriso", "-osirrox", "on", "-indev", image, "-extract", "/live/filesystem.squashfs", squash)
        run("sudo", "unsquashfs", "-no-progress", "-d", root, squash)
        run("xorriso", "-indev", image, "-report_el_torito", "plain")
        boot_image = image
    else:
        run("./ci/audit-ova.py", image, scratch)
        run("cp", scratch / "ova-audit.json", report)
        boot_image = scratch / "guest.vmdk"
        root.mkdir()
        run("sudo", "env", "LIBGUESTFS_BACKEND=direct", "guestmount", "--ro",
            "--format=vmdk", "-a", boot_image, "-i", root)
        mounted = True
    run("sudo", "./ci/audit-rootfs.py", root, report)
finally:
    if mounted:
        run("sudo", "guestunmount", root)

run("./ci/verify-boot.py", boot_image, target, report)
(report / "review-status.json").write_text(json.dumps({
    "offline_audit": "passed", "boot_review": "screenshots-awaiting-human-or-agent-review",
    "publication": "not-authorized-by-this-workflow", "target": target,
    "limits": "No physical hardware or actual VirtualBox runtime test in this QEMU lane",
}, indent=2) + "\n")
