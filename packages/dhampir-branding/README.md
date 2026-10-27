# dhampir-branding

The visible DhampirOS identity: login banner and welcome text.

## What is here

| File | What it does |
|---|---|
| `etc/issue.dhampir` | Text shown on the login screen. |
| `etc/motd.dhampir` | Short message shown after login. |
| `etc/dhampir_version` | Version string for DhampirOS. |
| `dhampir-branding.displace` | List of files that take the `.dhampir` version in place of the upstream one. |

## How it fits

Kicksecure ships its own files with a `.kicksecure` suffix, for example `/etc/issue.kicksecure`. Its `.displace` list says which files to swap. We follow the same pattern with `.dhampir`. We do not delete or rename any Kicksecure package.

## Not yet verified

- The swap is done by an external Debian helper, `config-package-dev`, which is not in this repository. Nothing here has been installed or tested on a real system yet.
- No `debian/` packaging exists yet, so this is not an installable `.deb`.
- The GRUB boot menu and the ISO splash screen are not changed yet.
