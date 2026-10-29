#!/usr/bin/python3
"""AI-Assisted. Test public images with enrolled-key Secure Boot and an unsigned control."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

from PIL import Image

REPOSITORY = "potemkin666/DhampirOS"
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "verification/secure-boot"
SCRATCH = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "dhampiros-secure-boot"
TARGET = os.environ["IMAGE_TARGET"]
if TARGET not in ("iso", "ova"):
    raise SystemExit("Unknown image target")
IMAGE = SCRATCH / f"DhampirOS-0.1.0-alpha.1-amd64.{TARGET}"


def run(*args):
    try:
        return subprocess.check_output([str(arg) for arg in args], text=True, stderr=subprocess.STDOUT, timeout=600)
    except subprocess.CalledProcessError as error:
        print(error.output[-12000:], file=sys.stderr)
        raise


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare():
    REPORT.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    release = json.loads((ROOT / "showcase/downloads.json").read_text())
    original = json.loads((ROOT / "release-reviews/v0.1.0-alpha.1.json").read_text())
    asset = release["assets"][TARGET]
    if (release["status"] != "published" or release["audit"] != "passed" or
            asset["url"] != f"https://github.com/{REPOSITORY}/releases/download/v0.1.0-alpha.1/{IMAGE.name}" or
            release["source_commit"] != original["source_commit"] or
            asset["sha256"] != original[TARGET]["sha256"]):
        raise SystemExit("Image identity differs from the reviewed release")
    run("git", "merge-base", "--is-ancestor", release["source_commit"], "HEAD")
    run("gh", "release", "download", "v0.1.0-alpha.1", "--repo", REPOSITORY,
        "--pattern", IMAGE.name, "--dir", SCRATCH)
    with IMAGE.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != asset["sha256"] or IMAGE.stat().st_size != asset["bytes"]:
        raise SystemExit("Image digest or size mismatch")
    attestation = json.loads(run(
        "gh", "attestation", "verify", IMAGE, "--repo", REPOSITORY,
        "--signer-workflow", f"{REPOSITORY}/.github/workflows/local-images.yml",
        "--source-digest", release["source_commit"], "--format", "json"))
    write_json(REPORT / "attestation-verification.json", attestation)
    write_json(REPORT / "image-identity.json", {
        "target": TARGET, "url": asset["url"], "sha256": digest,
        "bytes": IMAGE.stat().st_size, "source_commit": release["source_commit"],
    })
    root = SCRATCH / "rootfs"
    mounted = False
    try:
        if TARGET == "iso":
            squash = SCRATCH / "filesystem.squashfs"
            run("xorriso", "-osirrox", "on", "-indev", IMAGE,
                "-extract", "/live/filesystem.squashfs", squash)
            run("sudo", "unsquashfs", "-no-progress", "-d", root, squash)
            esp = SCRATCH / "iso-efi.img"
            run("xorriso", "-osirrox", "on", "-indev", IMAGE, "-extract", "/boot/grub/efi.img", esp)
            loaders = SCRATCH / "media-loaders"
            loaders.mkdir()
            run("mcopy", "-i", esp, "::/EFI/boot/*.efi", loaders)
        else:
            run(sys.executable, ROOT / "ci/audit-ova.py", IMAGE, SCRATCH)
            shutil.copyfile(SCRATCH / "ova-audit.json", REPORT / "ova-audit.json")
            root.mkdir()
            run("sudo", "env", "LIBGUESTFS_BACKEND=direct", "guestmount", "--ro",
                "--format=vmdk", "-a", SCRATCH / "guest.vmdk", "-i", root)
            mounted = True
            loaders = root / "boot/efi/EFI"
        # Guest root and ESP permissions are deliberately restrictive. Only the
        # offline host-side metadata reader needs root; no token is forwarded.
        run("sudo", "env", f"RUNNER_TEMP={os.environ['RUNNER_TEMP']}", f"IMAGE_TARGET={TARGET}",
            sys.executable, Path(__file__).resolve(), "offline")
    finally:
        if mounted:
            run("sudo", "guestunmount", root)
    print(f"Authenticated and inspected the public {TARGET}", flush=True)


def offline():
    root = SCRATCH / "rootfs"
    loaders = SCRATCH / "media-loaders" if TARGET == "iso" else root / "boot/efi/EFI"
    signatures = []
    for binary in [*loaders.rglob("*.efi"), *(root / "boot").glob("vmlinuz-*")]:
        # Only inspect packaged PE metadata; never run guest tools.
        if binary.resolve().is_relative_to(root) or binary.resolve().is_relative_to(SCRATCH / "media-loaders"):
            result = subprocess.run(["sbverify", "--list", str(binary)], text=True, capture_output=True)
            signatures.append({"file": str(binary.relative_to(SCRATCH)), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                               "returncode": result.returncode, "signature_metadata": result.stdout + result.stderr})
    write_json(REPORT / "pe-signatures.json", signatures)
    if TARGET == "iso":
        print(run(sys.executable, ROOT / "ci/audit-hardware.py", root,
                  ROOT / "hardware/targets/lenovo-83da.json", REPORT), flush=True)


def capture(label, media, secure, seconds, diagnostics=False):
    evidence = REPORT / label
    evidence.mkdir()
    code = Path("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
    template = Path("/usr/share/OVMF/OVMF_VARS_4M.ms.fd" if secure else "/usr/share/OVMF/OVMF_VARS_4M.fd")
    variables = SCRATCH / f"{label}-vars.fd"
    shutil.copyfile(template, variables)
    enrollment = run("virt-fw-vars", "--input", variables, "--print", "--verbose")
    (evidence / "firmware-vars.txt").write_text(enrollment)
    if secure and ("Microsoft" not in enrollment or "PK" not in enrollment):
        raise RuntimeError("Expected platform key and Microsoft trust certificates are missing")
    write_json(evidence / "firmware.json", {
        "code": str(code), "code_sha256": hashlib.sha256(code.read_bytes()).hexdigest(),
        "template": str(template), "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "secure_boot_requested": secure, "smm": True,
        "scope": "Distribution-supplied enrolled-key template; not every OEM key or current revocation database",
    })
    qmp_path = SCRATCH / f"{label}.sock"
    command = ["qemu-system-x86_64", "-machine", "q35,accel=kvm,smm=on", "-cpu", "host",
               "-m", "4096" if TARGET == "iso" and diagnostics else "2048", "-smp", "2",
               "-nic", "none", "-display", "none", "-snapshot", "-no-reboot",
               "-global", "driver=cfi.pflash01,property=secure,value=on",
               "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
               "-drive", f"if=pflash,format=raw,unit=1,file={variables}",
               "-qmp", f"unix:{qmp_path},server=on,wait=off",
               "-serial", f"file:{evidence / 'serial.log'}"]
    if media.suffix == ".iso":
        command += ["-cdrom", str(media), "-boot", "order=d"]
    else:
        command += ["-drive", f"file={media},format={'vmdk' if media.suffix == '.vmdk' else 'raw'},if=virtio"]
    write_json(evidence / "command.json", command)
    with (evidence / "qemu.log").open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        connection = socket.socket(socket.AF_UNIX)
        connection.settimeout(20)
        try:
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError("QEMU stopped before firmware startup")
                if qmp_path.exists():
                    break
                time.sleep(.5)
            connection.connect(str(qmp_path))
            stream = connection.makefile("rwb", buffering=0)
            json.loads(stream.readline())

            def qmp(execute, arguments=None):
                stream.write((json.dumps({"execute": execute, "arguments": arguments or {}}) + "\n").encode())
                while True:
                    response = json.loads(stream.readline())
                    if "error" in response:
                        raise RuntimeError(str(response["error"]))
                    if "return" in response:
                        return response["return"]

            def shot(name):
                ppm = evidence / f"{name}.ppm"
                qmp("screendump", {"filename": str(ppm)})
                with Image.open(ppm) as picture:
                    picture.save(evidence / f"{name}.png")
                ppm.unlink()

            def key(value):
                qmp("human-monitor-command", {"command-line": f"sendkey {value} 40"})

            def type_command(text):
                codes = {" ": "spc", "-": "minus", "/": "slash", ".": "dot"}
                for character in text:
                    key(codes.get(character, character))
                    time.sleep(.1)
                key("ret")

            qmp("qmp_capabilities")
            start = time.monotonic()
            for elapsed in seconds:
                time.sleep(max(0, start + elapsed - time.monotonic()))
                shot(f"boot-{elapsed}")
                if diagnostics and elapsed == 20:
                    key("ret")
            if diagnostics:
                shutil.copyfile(evidence / f"boot-{seconds[-1]}.png", evidence / "desktop-capture.png")
                key("meta_l-ret")
                time.sleep(15)
                key("alt-f10")
                time.sleep(5)
                # First terminal focus can absorb early keystrokes. Prime it
                # with a harmless command and read Secure Boot state last.
                type_command("clear")
                time.sleep(5)
                for name, text in (("kernel-version", "uname -r"),
                                   ("kernel-lockdown", "cat /sys/kernel/security/lockdown"),
                                   ("tirdad-state", "ls /sys/module/tirdad"),
                                   ("secure-boot-state", "mokutil --sb-state")):
                    key("ctrl-l")
                    type_command(text)
                    time.sleep(5)
                    shot(name)
                    ocr = run("tesseract", evidence / f"{name}.png", "stdout", "--psm", "6")
                    (evidence / f"{name}.txt").write_text(ocr)
            qmp("quit")
        finally:
            connection.close()
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=20)
    return evidence


def boot():
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise SystemExit("Only a disposable hosted runner may execute the firmware tests")
    if not (REPORT / "image-identity.json").is_file():
        raise SystemExit("Authenticate the image first")
    # A bootable, deliberately unsigned EFI control proves that the same
    # firmware executes it in setup mode and refuses it with enrolled keys.
    config = SCRATCH / "unsigned-grub.cfg"
    config.write_text("serial --unit=0 --speed=115200\nterminal_output serial console\necho DHAMPIROS_UNSIGNED_PROBE_EXECUTED\nsleep 120\nhalt\n")
    executable = SCRATCH / "unsigned-bootx64.efi"
    run("grub-mkstandalone", "--format=x86_64-efi", f"--output={executable}", f"boot/grub/grub.cfg={config}")
    listing = subprocess.run(["sbverify", "--list", str(executable)], text=True, capture_output=True)
    if "No signature table present" not in listing.stdout + listing.stderr:
        raise SystemExit("Negative control is not demonstrably unsigned")
    (REPORT / "unsigned-control-signatures.txt").write_text(listing.stdout + listing.stderr)
    probe = SCRATCH / "unsigned-probe.img"
    with probe.open("wb") as destination:
        destination.truncate(32 * 1024**2)
    run("mkfs.vfat", probe)
    run("mmd", "-i", probe, "::/EFI", "::/EFI/BOOT")
    run("mcopy", "-i", probe, executable, "::/EFI/BOOT/BOOTX64.EFI")
    off = capture("unsigned-control-off", probe, False, (20,))
    on = capture("unsigned-control-on", probe, True, (20,))
    marker = "DHAMPIROS_UNSIGNED_PROBE_EXECUTED"
    off_executed = marker in (off / "serial.log").read_text(errors="replace")
    on_executed = marker in (on / "serial.log").read_text(errors="replace")
    write_json(REPORT / "enforcement-control.json", {
        "unsigned_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "executes_with_setup_mode": off_executed, "executes_with_enrolled_keys": on_executed,
        "status": "passed" if off_executed and not on_executed else "failed",
    })
    if not off_executed or on_executed:
        raise SystemExit("Secure Boot rejection control failed")
    media = IMAGE if TARGET == "iso" else SCRATCH / "guest.vmdk"
    positive = capture("published-image", media, True, (20, 90, 240), diagnostics=True)
    state = (positive / "secure-boot-state.txt").read_text()
    enabled = bool(re.search(r"secure\s*boot\s+enabled", state, re.I))
    write_json(REPORT / "review-status.json", {
        "runtime_secure_boot_enabled_ocr": enabled, "unsigned_rejection_control": "passed",
        "desktop_review": "original screenshots require visual review",
        "physical_hardware": "not-tested", "publication": "not-authorized-by-this-workflow",
        "limitations": "OVMF enrolled-key template only; not every OEM firmware, revocation database or full verified root filesystem",
    })
    if not enabled:
        raise SystemExit("Guest Secure Boot enabled state was not captured; inspect original diagnostics")
    print("Enrolled-key unsigned rejection and guest Secure Boot enabled checks passed", flush=True)


if __name__ == "__main__":
    {"prepare": prepare, "offline": offline, "boot": boot}[sys.argv[1]]()
