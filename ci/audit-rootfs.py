#!/usr/bin/python3
"""AI-Assisted. Read-only release gate for an extracted DhampirOS filesystem.

Run in a disposable Linux verifier, never by executing programs from the image.
This records bounded checks, not a claim of absence of vulnerabilities.
"""

import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit

root = Path(sys.argv[1]).resolve(strict=True)
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)
checks = []


def check(name, passed):
    checks.append({"check": name, "passed": bool(passed)})


def guest_path(name):
    """Resolve absolute guest symlinks inside the guest, with a bounded walk."""
    parts = list(Path(name.lstrip("/")).parts)
    resolved = []
    links = 0
    while parts:
        part = parts.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            if not resolved:
                raise ValueError("Guest path escapes filesystem")
            resolved.pop()
            continue
        candidate = root.joinpath(*resolved, part)
        if candidate.is_symlink():
            links += 1
            if links > 40:
                raise ValueError("Guest symlink loop")
            target = candidate.readlink()
            if target.is_absolute():
                resolved = []
            parts = list(target.parts[1:] if target.is_absolute() else target.parts) + parts
        else:
            resolved.append(part)
    return root.joinpath(*resolved)


def read(name):
    path = guest_path(name)
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def active(text):
    return "\n".join(line.split("#", 1)[0].strip() for line in text.splitlines())


status = read("/var/lib/dpkg/status")
packages = {}
for paragraph in status.split("\n\n"):
    fields = dict(re.findall(r"^([A-Za-z-]+): (.*)$", paragraph, re.M))
    if fields.get("Status") == "install ok installed":
        packages[fields["Package"]] = fields.get("Version", "unknown")
check("full desktop package inventory", len(packages) > 500)
for package in ("dhampir-branding", "dhampiros-artwork", "dhampiros-motion",
                "security-misc-shared", "security-misc-desktop", "apparmor",
                "apparmor-profile-dist", "user-sysmaint-split"):
    check(f"installed: {package}", package in packages)
check("Dhampir desktop meta package", any(
    name in packages for name in ("dhampir-vm-gui-lxqt", "dhampir-baremetal-gui-lxqt")
))
(output / "packages.json").write_text(json.dumps(packages, indent=2, sort_keys=True) + "\n")

for asset in ("/usr/share/backgrounds/dhampiros/nocturne-rider.jpg",
              "/usr/share/dhampiros/motion/transparent.png",
              "/usr/share/dhampiros/motion/nocturne-rider-1080p.webm",
              "/usr/share/dhampiros/motion/nocturne-rider-720p-light.webm"):
    check(f"installed visual resource: {asset}", guest_path(asset).is_file())

check("DhampirOS identity", "DhampirOS" in read("/etc/issue") and
      bool(read("/etc/dhampir_version").strip()))
grub = active(read("/boot/grub/grub.cfg"))
check("bootloader configuration exists", "menuentry" in grub)
check("no SMBIOS command-line injection in bootloader", not re.search(
    r"dm-smbios|smbios.*--get-string|smbios.*--get-byte", grub, re.I
))
check("no debug root shell in boot entries", not re.search(
    r"(?:init|rdinit)=/(?:usr/)?(?:s?bin)/(?:ba)?sh|systemd.debug_shell|rd.break", grub
))
check("AppArmor not disabled at boot", not re.search(r"apparmor=0|security=none", grub))
for parameter in ("mitigations=auto,nosmt", "slab_nomerge", "init_on_alloc=1"):
    check(f"inherited boot hardening: {parameter}", parameter in grub)
if len(sys.argv) > 3:
    iso_boot = active(Path(sys.argv[3]).read_text())
    check("ISO does not load SMBIOS debug arguments", "dm_smbios_extra" not in iso_boot)
    for parameter in ("mitigations=auto,nosmt", "slab_nomerge", "init_on_alloc=1"):
        check(f"ISO live boot hardening: {parameter}", parameter in iso_boot)

apt_config = []
for path in guest_path("/etc/apt").rglob("*"):
    if path.is_file() and path.suffix in (".conf", ".list", ".sources", ""):
        apt_config.append(active(read("/" + str(path.relative_to(root)))))
apt_text = "\n".join(apt_config)
source_details = []
for path in guest_path("/etc/apt").rglob("*"):
    if path.is_file() and path.suffix in (".list", ".sources"):
        text = active(read("/" + str(path.relative_to(root))))
        uris = re.findall(r"(?:[A-Za-z+]+)://[^\s]+", text)
        public_uris = []
        for uri in uris:
            parsed = urlsplit(uri)
            public_uris.append(urlunsplit((parsed.scheme, parsed.netloc.rsplit("@", 1)[-1],
                                          parsed.path, "", "")))
        source_details.append({"file": str(path.relative_to(root)), "uris": public_uris,
                               "enabled": re.findall(r"^Enabled:\s*(.*)$", text, re.M),
                               "suites": re.findall(r"^Suites:\s*(.*)$", text, re.M)})
check("APT does not disable authentication", not re.search(
    r'AllowUnauthenticated\s+["\s]*true|AllowInsecureRepositories\s+["\s]*true|'
    r'trusted\s*=\s*yes|Trusted:\s*yes|Allow-Unauthenticated:\s*yes', apt_text, re.I
))
check("Debian security updates configured", "debian-security" in apt_text or "trixie-security" in apt_text)
check("Kicksecure update repository configured", "kicksecure" in apt_text.lower())

check("machine ID regenerated on first boot", not read("/etc/machine-id").strip())
check("D-Bus machine ID regenerated on first boot", not read("/var/lib/dbus/machine-id").strip())
for seed in ("/var/lib/systemd/random-seed", "/var/lib/urandom/random-seed", "/var/lib/random-seed"):
    path = guest_path(seed)
    check(f"no cloned entropy seed: {seed}", not path.exists() or path.stat().st_size == 0)
ssh = guest_path("/etc/ssh")
check("no cloned SSH host private keys", not any(ssh.glob("ssh_host_*_key")))
check("no enabled SSH server socket", not guest_path(
    "/etc/systemd/system/sockets.target.wants/ssh.socket").exists())

accounts = []
for row in read("/etc/shadow").splitlines():
    fields = row.split(":")
    if len(fields) > 1:
        name, secret = fields[:2]
        state = "locked" if secret.startswith(("!", "*")) else "empty" if not secret else "password-set"
        accounts.append({"account": name, "password_state": state})
        if name == "root":
            check("root password locked", state == "locked")
check("shadow account policy readable", any(a["account"] == "root" for a in accounts))
for home in ("/root", "/home"):
    paths = list(guest_path(home).rglob("authorized_keys"))
    check(f"no pre-authorized SSH access in {home}", not any(
        read("/" + str(path.relative_to(root))).strip() for path in paths
    ))
    for credential in (".git-credentials", ".netrc", "id_rsa", "id_ed25519"):
        check(f"no builder credential {home}/{credential}", not any(
            guest_path(home).rglob(credential)
        ))

report = {
    "status": "passed" if all(c["passed"] for c in checks) else "failed",
    "checks": checks, "accounts": accounts,
    "configuration_evidence": {
        "apt_sources": source_details,
        "machine_ids": {name: read(name).strip() for name in
                        ("/etc/machine-id", "/var/lib/dbus/machine-id")},
    },
    "scope": "Offline package, update, boot configuration, host key and credential checks",
    "limitations": ["No guarantee of safety or absence of vulnerabilities",
                    "Boot and desktop interaction require separate verification",
                    "Standard upstream user autologin and account setup must be reviewed"],
}
(output / "rootfs-audit.json").write_text(json.dumps(report, indent=2) + "\n")
for item in checks:
    print(("PASS " if item["passed"] else "FAIL ") + item["check"])
sys.exit(0 if report["status"] == "passed" else 1)
