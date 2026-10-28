# DhampirOS theme asset integration

The user supplied a validated DhampirOS asset pack on 2026-10-27.

## What is integrated

The source package `packages/dhampir/dhampiros-artwork/` installs the pack's validated rootfs overlay. The overlay contains DhampirOS icons, cursor themes, LXQt and labwc theme resources, GRUB theme resources, backgrounds, boot artwork, fonts and sounds under `/usr/share`.

The `dhampir-vm-gui-lxqt` and `dhampir-baremetal-gui-lxqt` meta packages depend on `dhampiros-artwork`.

The package intentionally does not replace Kicksecure authentication, hardening, session policy, kernel arguments or network configuration.

## Importing the binary payload

The GitHub connector used for the initial integration cannot upload the binary archive itself. From a local checkout, run:

```bash
python3 packages/dhampir/dhampiros-artwork/import-assets.py "/path/to/vampire hunter d.zip"
```

This extracts only the purpose-built `DhampirOS-Linux-Assets/DhampirOS-rootfs-overlay.tar.gz` payload to:

```text
packages/dhampir/dhampiros-artwork/assets/rootfs-overlay.tar.gz
```

The loose `art/` JPEG reference folder is deliberately ignored.

Commit that one generated archive after reviewing it. The Debian package build fails clearly if it is absent.

## Provenance supplied with the pack

The pack states that its new illustrations were generated for DhampirOS, its vectors and event sounds are original, Cinzel is supplied under the OFL, and a supplied Vampire Hunter D still was used only as visual reference and is not bundled in the DhampirOS asset payload.

## Still to wire up

Installing artwork is separate from selecting it as the default. The `dhampiros-artwork` 0.2 package ships system-wide defaults for new users (`/etc/skel` LXQt `lxqt.conf`, pcmanfm-qt wallpaper, QTerminal `DhampirNocturne` colour scheme). These are visual only. Not yet wired: GRUB (`GRUB_THEME` is left to the upstream Kicksecure drop-in), cursor, Plymouth, login/greetd, and labwc, because the tracked `source-rootfs` payload has no assets for them. Login/greetd integration must merge only visual values and preserve upstream authentication/session behaviour.

The static test `packages/dhampir/dhampiros-artwork/tests/test-theme-paths.sh` checks that every configured path exists in `assets/source-rootfs` and runs during `debian/rules override_dh_auto_test`.
