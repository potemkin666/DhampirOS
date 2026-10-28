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
audit_args = []
failed_gates = []
try:
    if target == "iso":
        squash = scratch / "filesystem.squashfs"
        run("xorriso", "-osirrox", "on", "-indev", image, "-extract", "/live/filesystem.squashfs", squash)
        run("sudo", "unsquashfs", "-no-progress", "-d", root, squash)
        run("xorriso", "-indev", image, "-report_el_torito", "plain")
        run("xorriso", "-osirrox", "on", "-indev", image, "-extract", "/boot/grub", report / "iso-grub")
        iso_config = report / "iso-boot-config.cfg"
        run("xorriso", "-osirrox", "on", "-indev", image, "-extract", "/boot/grub/config.cfg", iso_config)
        audit_args.append(iso_config)
        boot_image = image
    else:
        run("./ci/audit-ova.py", image, scratch)
        run("cp", scratch / "ova-audit.json", report)
        boot_image = scratch / "guest.vmdk"
        root.mkdir()
        run("sudo", "env", "LIBGUESTFS_BACKEND=direct", "guestmount", "--ro",
            "--format=vmdk", "-a", boot_image, "-i", root)
        mounted = True
    audit = subprocess.run([str(arg) for arg in ("sudo", "./ci/audit-rootfs.py", root, report, *audit_args)],
                           check=False)
    if audit.returncode:
        failed_gates.append("offline filesystem audit")
    with (report / "debian-vulnerability-report.txt").open("w") as vulnerabilities:
        subprocess.run(["sudo", "debsecan", "--suite", "trixie", "--status",
                        str(root / "var/lib/dpkg/status"), "--format", "detail"],
                       check=True, stdout=vulnerabilities)
    fixable = subprocess.check_output([
        "sudo", "debsecan", "--suite", "trixie", "--status", str(root / "var/lib/dpkg/status"),
        "--format", "packages", "--only-fixed",
    ], text=True).splitlines()
    (report / "security-update-gate.json").write_text(json.dumps({
        "suite": "trixie", "packages_with_security_fixes_available": fixable,
        "status": "failed" if fixable else "passed",
        "scope": "Debian tracker coverage only; custom packages and unfixed findings need separate review",
    }, indent=2) + "\n")
    if fixable:
        failed_gates.append("available security fixes")
finally:
    if mounted:
        run("sudo", "guestunmount", root)

run("./ci/verify-boot.py", boot_image, target, report)
if failed_gates:
    raise SystemExit("Publication blocked by: " + ", ".join(failed_gates))
(report / "review-status.json").write_text(json.dumps({
    "offline_audit": "passed", "boot_review": "screenshots-awaiting-human-or-agent-review",
    "publication": "not-authorized-by-this-workflow", "target": target,
    "limits": "No physical hardware or actual VirtualBox runtime test in this QEMU lane",
}, indent=2) + "\n")
