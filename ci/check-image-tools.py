#!/usr/bin/python3
"""AI-Assisted. Basic release tool syntax and malicious archive smoke checks."""

import ast
import hashlib
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile

import yaml

for pattern in ("image-*.py", "audit-*.py", "verify-*.py", "prepare-image-release.py", "publish-image-release.py", "check-image-tools.py"):
    for script in Path("ci").glob(pattern):
        ast.parse(script.read_text())
for workflow in Path(".github/workflows").glob("local-image*.yml"):
    yaml.safe_load(workflow.read_text())
shell_scripts = ["ci/image-host.sh", "ci/image-container.sh", "ci/check-image-packages.sh"]
subprocess.run(["bash", "-n", *shell_scripts], check=True)
subprocess.run(["shellcheck", *shell_scripts], check=True)

with tempfile.TemporaryDirectory(prefix="dhampiros-tool-check-") as temporary:
    scratch = Path(temporary)
    descriptor = (
        b'<Envelope><VirtualSystem><Machine><Hardware><Memory RAMSize="2048"/><CPU count="3"/><Network>'
        b'<Adapter enabled="true"><NAT/></Adapter></Network>'
        b'<Clipboard mode="Disabled"/><DragAndDrop mode="Disabled"/>'
        b'</Hardware></Machine></VirtualSystem></Envelope>'
    )
    disk = b"TOY STRUCTURAL FIXTURE; NOT AN OS IMAGE"
    manifest = b"".join(
        f"SHA256 ({name}) = {hashlib.sha256(data).hexdigest()}\n".encode()
        for name, data in (("guest.ovf", descriptor), ("guest.vmdk", disk))
    )
    for scenario in ("valid", "inactive-modes", "bridged", "forwarded", "traversal", "symlink", "changed-disk"):
        appliance = scratch / f"{scenario}.ova"
        scenario_descriptor = descriptor
        if scenario == "inactive-modes":
            scenario_descriptor = descriptor.replace(
                b"<NAT/>", b'<DisabledModes><BridgedInterface name="eth0"/><NATNetwork/></DisabledModes><NAT/>')
        elif scenario == "bridged":
            scenario_descriptor = descriptor.replace(b"<NAT/>", b'<BridgedInterface name="eth0"/>')
        elif scenario == "forwarded":
            scenario_descriptor = descriptor.replace(b"<NAT/>", b'<NAT><Forwarding hostport="2222" guestport="22"/></NAT>')
        scenario_manifest = manifest.replace(
            hashlib.sha256(descriptor).hexdigest().encode(),
            hashlib.sha256(scenario_descriptor).hexdigest().encode())
        files = [("guest.ovf", scenario_descriptor), ("guest.vmdk", disk), ("guest.mf", scenario_manifest)]
        if scenario == "traversal":
            files.append(("../host-file", b"unacceptable"))
        if scenario == "changed-disk":
            files[1] = ("guest.vmdk", b"modified payload")
        with tarfile.open(appliance, "w") as archive:
            for name, data in files:
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            if scenario == "symlink":
                link = tarfile.TarInfo("host-file")
                link.type = tarfile.SYMTYPE
                link.linkname = "/etc/passwd"
                archive.addfile(link)
        result = subprocess.run(["./ci/audit-ova.py", str(appliance), str(scratch / scenario)],
                                capture_output=True, text=True)
        if (result.returncode == 0) != (scenario in ("valid", "inactive-modes")):
            raise SystemExit(f"Unexpected OVA result for {scenario}: {result.stderr}")
    (scratch / "Dhampir.iso").write_bytes(b"placeholder")
    result = subprocess.run(["./ci/image-collect.py", str(scratch), "iso"], capture_output=True, text=True)
    if result.returncode == 0 or "too small" not in result.stderr:
        raise SystemExit("Placeholder image was not rejected")

print("PASS: syntax, shellcheck, manifest integrity, active networking policy, traversal/symlink rejection, placeholder rejection")
