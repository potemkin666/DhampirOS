# Secure Boot and hardware verification (AI-Assisted)

## Test boundary

The public 0.1.0-alpha.1 ISO and OVA are immutable inputs. The verifier checks
their exact reviewed digest, size, original source ancestry and workflow
attestation. Host tools inspect PE signature metadata and filesystems without
running guest binaries. Only the offline reader uses root for protected root
and ESP paths; the download token is not forwarded into that process or the
guest boot step.

QEMU uses KVM, Q35, SMM and protected pflash with the distribution's enrolled
Microsoft-key OVMF template. Exact firmware and template hashes, PK/KEK/db/dbx
metadata and command lines are retained. The supplied template includes 2011
and 2023 Microsoft authorities. It is not every OEM firmware or a claim that
its dbx represents every current revocation.

A deliberately unsigned GRUB EFI control prints a unique serial marker in
setup mode. The same binary must not execute with the enrolled-key template;
original displays of its rejection are retained. A missing marker alone does
not approve the image: the public image must separately reach its desktop,
report `SecureBoot enabled` through the normal user terminal and show kernel
lockdown. All original captures require visual review. No root serial login,
custom trusted MOK, unsigned boot bypass or image modification is introduced.

Secure Boot here concerns the firmware-to-kernel chain. No verified root
filesystem, dm-verity, UKI or complete initramfs authentication is added. Do
not describe a successful boot as complete verified boot or certification.

## Observed diagnostic handling

Initial metadata inspection from the ordinary runner user could not traverse
the guest's deliberately protected root and ESP. The separate host-side
offline reader handles that; guest permissions are retained. The first
terminal command also lost input while QTerminal acquired focus. A harmless
warm-up and reading Secure Boot state last correct that automation issue.
An incomplete diagnostic is not evidence of a missing command or disabled
Secure Boot. Preserve raw failed-attempt evidence separately.

An enforcing test showed kernel integrity lockdown with no loaded `tirdad`
module. Record that observation and its limits explicitly. No matched
Secure-Boot-off module-loading comparison was performed, so do not assert a
newly proven cause. Upstream discusses this module limitation at
https://forums.kicksecure.com/t/secure-boot-invalid-signature/771 . Do not
disable signature verification or weaken module policy to make a check pass.

## Hardware boundary and privacy

The owner selected the current Lenovo 83DA, Core Ultra 7 155H, 16 GiB target.
The committed profile contains only common model and PCI identity data for
its NVMe controller, AX211 Wi-Fi and Arc graphics. It excludes serial numbers,
device-instance paths, user names, MAC/IP addresses and host names. Matching
kernel PCI aliases, module signatures and firmware inventory are inspection
results, not proof that devices initialize or work physically.

`hardware/collect-live-evidence.py` collects read-only local observations from
a future Linux live session. It never writes disks or firmware, invokes no
network operation, uploads nothing, excludes personal device identifiers and
creates only an explicitly selected new JSON file with mode 0600. Existing
files and symlinks are rejected. Functional display, Wi-Fi, audio, touchpad,
suspend, battery and installation checks remain `not-tested` automatically.

A selected drive letter is not authorization to erase a drive. No USB media
has been prepared or modified by this work. Physical testing remains pending
until a separately identified suitable boot medium and the owner's consent
are available. Preserve all existing data drives.

## Reviewed run

Run `40858979567`, verifier source
`99d908dbc8c0c75edeca88f184b9f2e934d37d51`, passed both targets. Original
desktop, Secure Boot enabled, integrity-lockdown, `tirdad`-absence and
unsigned-rejection captures were viewed for both images. The exact review
and file hashes are in `release-reviews/v0.1.0-alpha.1-secure-boot.json`.

Kernel `6.12.113+deb13-amd64` has matching `nvme`, `iwlwifi`, `i915` and `xe`
modules for the selected three PCI devices. Firmware alternatives are listed
without claiming every modinfo entry is required. The standalone collector's
syntax/help and Windows refusal/no-output guard were checked. It has not
been used to claim a physical Linux result on the Lenovo.

The release supplement retains the complete original evidence, signature
metadata, firmware trust inventory, original image identities, hardware
inventory and checksums. Original reports are historical snapshots and are
not overwritten. Only the earlier untested-Secure-Boot statement is superseded
for this specific VM lane; physical and other stated limits remain.
