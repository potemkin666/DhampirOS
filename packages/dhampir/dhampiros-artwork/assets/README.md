# DhampirOS artwork payloads

This package supports two artwork sources:

1. `source-rootfs/` — a small, tracked, source-first fallback containing the DhampirOS vector wallpaper, LXQt styling, menu/icon identity, palette and a source-only GRUB theme. This is sufficient for development and lets the Debian package build without a large binary archive.
2. `rootfs-overlay.tar.gz` — the optional full validated artwork payload from the supplied DhampirOS asset pack. When present, the package build prefers this archive and installs the complete raster/cursor/sound artwork set.

The full archive SHA256 is:

`24def36263c99f32f57ba90e00efbb2292522972af928fce357c0ff2abb4da22`

Use `../import-assets.py /path/to/vampire hunter d.zip` to extract and validate the full archive locally.

The loose movie-reference JPEGs outside the purpose-built DhampirOS asset pack are not imported.
