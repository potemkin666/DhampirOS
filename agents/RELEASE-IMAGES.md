# Image release engineering notes (AI-Assisted)

No downloadable images had been published when this work started on
2026-10-28. The website catalogue deliberately remains `building/pending`
until real release assets and their verification evidence exist. Never set
`published/passed` merely because scripts parse, packages build or an Actions
job is green.

## Build and trust boundary

`local-images.yml` first checks all four isolated Dhampir source packages with
lintian failing on errors and warnings. The full `dhampir-lxqt` ISO and
VirtualBox targets then run on disposable amd64 Linux runners, using the
upstream pinned Docker build environment and pinned submodules. Guest APT
freshness is `current`; signed upstream update repositories remain enabled.
There is no SMBIOS debug reader, serial-login test backdoor, unsigned-source
verification bypass, tiny CI flavor or dry-run image.

The upstream EOF-newline checker mistakes binary artwork for text. The
tracked `patches/dhampir-binary-eof.patch` corrects only that binary handling;
the Unicode, modeline, whitespace and clean-source checks remain active.
The patch is applied in the disposable build checkout before signing and is
recorded with the original commit, original submodule pins and patch digest.
It does not change the checked-in upstream gitlink.

The upstream CI signing helpers mint an ephemeral build identity and amend
their disposable checkout. These are internal consistency signatures, not
official Kicksecure release signatures or a long-term offline Dhampir key.
GitHub OIDC image attestations independently identify this repository,
workflow and original source commit. Attestations establish origin, not the
absence of vulnerabilities. Never upload private CI signing keys.

Package-specific lintian overrides cover exact `/etc/skel` visual defaults
for newly created distribution accounts. They do not modify existing homes.
The desktop command's manual-page override follows this repository's policy
against AI-authored end-user feature documentation. Other packaging errors
and warnings still fail closed.

## Independent verification

`local-image-verification.yml` waits for a successful owner-repository image
run, verifies its workflow identity and source ancestry, downloads the exact
artifacts and checks their SHA-256 and size before inspecting them.

The verifier executes no tools from the guest filesystem. It inspects ISO
squashfs or read-only libguestfs mounts, validates the OVA tar paths and
manifest, and checks NAT with clipboard, drag/drop, host shares and remote
display disabled. The offline report checks required security packages,
authenticated APT updates, inherited GRUB hardening, no debug root shell,
cloned host keys/identifiers and builder credentials. Debian's vulnerability
report is retained and available security fixes block release.

BIOS and UEFI QEMU boots have no network, use snapshot disks and capture
screens without enabling root serial login. The screenshots require actual
review. `review-status.json` explicitly says this; it is not a release
approval. Physical hardware and actual VirtualBox runtime compatibility
remain separate checks. Debian tracker coverage does not cover every custom
package or guarantee safety.

## Publication requirements

Publish only actual reviewed images, as an experimental prerelease, with
SHA-256 sums, exact source/build links, package inventories, vulnerability
findings, bounded verification results and remaining limitations. GitHub
Release assets must be below its per-file limit; inspect actual sizes before
choosing delivery. Keep binaries out of Git. Enable the website catalogue
only after both public assets and report/checksum links work.

The catalogue validates all metadata before enabling either image link;
missing metadata or an unexpected download host leaves both disabled.
Local browser checks covered desktop and mobile layouts, pending catalogue,
valid catalogue, unsafe URL rejection and the existing interactive preview.
Use a static server with correct MIME types and byte-range support for the
video preview. The Windows Python stock server produced incomplete image
loads; a Node static/range server passed with the same unchanged images.
