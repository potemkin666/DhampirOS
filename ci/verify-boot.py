#!/usr/bin/python3
"""AI-Assisted. Capture network-isolated BIOS/UEFI boots without root backdoors."""

import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

from PIL import Image

image = Path(sys.argv[1]).resolve()
target = sys.argv[2]
report = Path(sys.argv[3]).resolve()
resources = {"memory_mib": 3072, "processors": 2}
if target == "virtualbox":
    resources = json.loads((report / "ova-audit.json").read_text())

for firmware in ("bios", "uefi"):
    evidence = report / firmware
    evidence.mkdir()
    qmp_path = evidence / "qmp.sock"
    command = ["qemu-system-x86_64", "-machine", "q35,accel=tcg", "-cpu", "max",
               "-m", str(resources["memory_mib"]), "-smp", str(resources["processors"]),
               "-nic", "none", "-display", "none",
               "-qmp", f"unix:{qmp_path},server=on,wait=off", "-no-reboot", "-snapshot",
               "-serial", f"file:{evidence / 'serial.log'}"]
    if firmware == "uefi":
        code = Path("/usr/share/OVMF/OVMF_CODE_4M.fd")
        variables = evidence / "OVMF_VARS.fd"
        shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", variables)
        command += ["-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
                    "-drive", f"if=pflash,format=raw,unit=1,file={variables}"]
    if target == "iso":
        command += ["-cdrom", str(image), "-boot", "order=d"]
    else:
        command += ["-drive", f"file={image},format=vmdk,if=virtio"]
    with (evidence / "qemu.log").open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        connection = socket.socket(socket.AF_UNIX)
        connection.settimeout(20)
        try:
            for _ in range(40):
                if process.poll() is not None:
                    raise RuntimeError("QEMU exited before startup")
                if qmp_path.exists():
                    break
                time.sleep(0.5)
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

            qmp("qmp_capabilities")
            start = time.monotonic()
            for elapsed in (20, 90, 240):
                time.sleep(max(0, start + elapsed - time.monotonic()))
                ppm = evidence / f"boot-{elapsed}.ppm"
                qmp("screendump", {"filename": str(ppm)})
                with Image.open(ppm) as frame:
                    frame.save(evidence / f"boot-{elapsed}.png")
                ppm.unlink()
                if elapsed == 20:
                    qmp("human-monitor-command", {"command-line": "sendkey ret"})
            qmp("quit")
        finally:
            connection.close()
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=20)
