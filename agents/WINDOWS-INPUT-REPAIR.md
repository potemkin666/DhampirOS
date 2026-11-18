# Windows VirtualBox input compatibility (AI engineering notes)

The reported Windows desktop loses both Bluetooth inputs while booting the
public ISO in VirtualBox. The user says Windows remains unresponsive.
This does not establish whether input transport disappeared or the host hung.
The user-supplied 2026-11-18 report shows VirtualBox 7.2.6 on Windows 11,
Hyper-V/NEM active, no global USB filters, and two active VM USB filters on
one of two registered VMs with non-Dhampir names. Filter identities are not
in the report, so capture of a Bluetooth adapter is plausible, not proven.
The accessible machine has no registered/default VirtualBox installation or
VM registry. Do not describe this repair as applied to that desktop or its
reported fault as reproduced/resolved. Keep the raw report private.

`tools/windows/Fix-input.cmd` applies a bounded, reversible host VM profile:
PS/2 keyboard/mouse, all VM USB filters/controllers off, 3D acceleration off.
Physical Bluetooth/receiver devices remain under host control for this VM.
The profile follows the input/USB isolation used in the existing native boot
verifier; disabling 3D is an additional conservative host graphics baseline.
This is a mitigation, not proof of a root cause or Windows compatibility.

The tool uses the installed VBoxManage API rather than editing a registered
`.vbox` file. It selects a VM by Dhampir name or attached DhampirOS ISO; an
ambiguous or unrecognised name requires explicit selection. Running, paused
and saved-state VMs are refused. It backs up the original configuration and
six touched settings and filter activation before mutation, verifies the
resulting XML, and tries to restore those settings on failure. Undo restores
only those settings through VBoxManage; it does not overwrite newer unrelated
VM settings. A changed filter list blocks Undo rather than enabling a newly
added device filter by mistake.

No VM is started, disk image rewritten, USB media formatted, Windows driver
changed, host security feature disabled or data uploaded. Backups contain
local VM configuration and should stay private. The launcher sets execution
policy only for its PowerShell process, not the Windows installation.

Validation is PowerShell 5.1 parsing and a mock VBoxManage integration check:
USB profiles, CLI option variants, backup, undo, failure recovery, selection
and refusal of running/saved VMs. Actual Windows VirtualBox interactive and
Bluetooth input verification remain pending. Published image bytes and their
original verification evidence are unchanged.

## USB launch path

The USB also includes `Start-DhampirOS.cmd`. It verifies the original ISO's
exact size/SHA-256, then creates or reuses only a marked `DhampirOS USB Live`
VM. Configuration/logs are host-local under LOCALAPPDATA; the ISO is read
from the USB as a virtual DVD, never passed through as physical USB media.
It uses 4 GiB/2 vCPUs, BIOS, VMSVGA without 3D, PS/2 input, no USB capture,
NAT, and disabled clipboard/drag-drop/VRDE. It creates no virtual hard disk;
this is an ephemeral live session. Other running VMs block launch. An existing
unmarked VM with the same name is refused. The launcher is tested with a
mock CLI; actual Windows VirtualBox input/freeze resolution remains pending.

On 2026-11-18 the connected USB was reidentified as D:, Verbatim STORE N GO,
115 GiB FAT32, non-boot/non-system USB disk, containing the original
`DhampirOS` image folder and supplied diagnostic report. This is not the
earlier Toshiba data disk associated with D:. User explicitly requested
copying the fix to the connected USB. Add files only; do not format media,
change partitions or rewrite the existing ISO/OVA. Never infer identity
from the drive letter alone on subsequent runs.

Primary references checked on 2026-11-18:
- https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/vboxmanage.html#vboxmanage-modifyvm
- https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html#settings-usb
