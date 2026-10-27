# How DhampirOS is built

This page explains, in plain language, how we will build `Dhampir.iso` and `Dhampir.ova`. It lives under `agents/` because `AGENTS.md` does not allow a `docs/` directory.

**Status: not yet working.** The steps below come from the upstream `derivative-maker` tool. They have not yet been run end-to-end for DhampirOS. Each step will be marked as tested here once it is.

## The short version

1. We use **derivative-maker**, the official Kicksecure build tool, to build the system.
2. We feed it the Kicksecure packages and our Dhampir branding.
3. It produces either an ISO (a bootable disk image) or an OVA (a ready-made VirtualBox virtual machine).
4. The output files are uploaded as **GitHub Release assets**. They are never committed to Git.

## Words used in this guide

- **ISO**: a single file that acts like a DVD or USB stick. You boot from it to try or install the system.
- **OVA**: a single file that holds a complete virtual machine for VirtualBox. You import it with *File → Import Appliance*.
- **Flavor**: a named build recipe, for example `kicksecure-cli` (text only) or `kicksecure-lxqt` (desktop).
- **Target**: the kind of output you want, for example `iso` or `virtualbox`.
- **Submodule**: another Git repository stored inside this one. The `packages/kicksecure/*` folders are submodules.

## What each part of the repo does

| Item | Plain-language role |
|---|---|
| `derivative-maker` | The main build script. You run it and tell it what to build. |
| `build-steps.d/` | Numbered scripts that `derivative-maker` runs in order. For example `4310_convert-raw-to-iso` makes the ISO. |
| `variables.d/` | Scripts that work out settings such as the flavor name and the package list. |
| `help-steps/` | Helper scripts used by the build steps. |
| `iso-build-data/` | Files for the ISO boot menu (GRUB). |
| `packages/kicksecure/` | Upstream Kicksecure packages (submodules). Do not edit these here. |
| `packages/dhampir-branding/` | Our package with the Dhampir name, text and colours. |
| `branding/` | Source notes for the Dhampir look: names and colour palette. |
| `config/` | Our build settings, layered on top of upstream defaults. |
| `kernel/` | Reserved for the future custom kernel. Empty for now. |

## Step 0: prepare the build machine

Builds must run on **Debian** (or Kicksecure) with root access, and need a lot of disk space and a fast network. Upstream recommends using their Docker image so the host stays clean.

Before anything else, download the submodules. Without them the tool stops with an error:

```
git submodule update --init --recursive --progress --jobs=4
```

We verified that `./derivative-maker` refuses to run until this is done.

## Step 1: pick a flavor and a target

Upstream examples use:

```
sudo ./derivative-maker --flavor kicksecure-cli --target iso
sudo ./derivative-maker --flavor kicksecure-cli --target virtualbox
```

- `--target iso` produces a bootable ISO.
- `--target virtualbox` produces a VirtualBox image. The `.ova` is made inside a Debian chroot, so VirtualBox does not need to be installed on the build machine.

The `dhampir` flavor name is **planned, not yet added**. Until it is, the commands above build upstream Kicksecure, not DhampirOS.

## Step 2: what happens during a build

In broad terms, `derivative-maker`:

1. Checks the machine and settings.
2. Builds any Debian packages it needs.
3. Creates a root filesystem with the Kicksecure packages installed.
4. Converts that filesystem into an ISO (GRUB boot menu plus live system) or into a VirtualBox disk.
5. Checks that the kernel hardening settings were kept.

Step 5 matters for us. It fails the build if the hardening options are missing from the boot config.

## Step 3: check the output

- Compare the file's checksum against the one published with the release.
- For the ISO, boot it in a VM and check that the boot menu shows DhampirOS.
- For the OVA, import it into VirtualBox and check that it starts.

## Step 4: publish

Upload `Dhampir.iso` and `Dhampir.ova` as GitHub Release assets. The `.gitignore` file already blocks these file types from being committed.

## Dry runs

`derivative-maker` supports a dry run (`--dry-run true`). It creates placeholder files instead of real images. Use it to check that the settings are read correctly. It does not prove the image works.

## Open questions

- How to add a `dhampir` flavor cleanly to `derivative-maker`.
- Whether a custom kernel (later phase) needs a separate build step.
