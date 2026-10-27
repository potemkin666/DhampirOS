# DhampirOS

DhampirOS is a hardened Linux distribution based on **Kicksecure**, which is itself based on **Debian**. Its short name is **Dhampir**.

The visual theme is inspired by *Vampire Hunter D*: gothic, restrained, dark, with silver, ivory and oxblood accents.

> DhampirOS is an independent project. It is not made by, and not endorsed by, the Kicksecure or Whonix developers.

## Core rule: keep the hardening

Kicksecure's security and hardening features are the reason this project exists.

- DhampirOS **adds** branding and configuration on top of Kicksecure.
- Changes must **not remove or weaken** Kicksecure security features, for example kernel hardening flags, sandboxing, firewall rules, or package hardening.
- Where possible, Dhampir-specific code lives in its own files (for example `*.dhampir` files and `packages/dhampir-branding/`), so upstream files stay intact and easy to compare.

## What it is built from

This repository is a fork of [`derivative-maker`](https://github.com/Kicksecure/derivative-maker), the official Kicksecure build tool. `derivative-maker` is the program that turns Debian packages into a bootable image. DhampirOS uses it, and adds its own layer on top.

Layers, from bottom to top:

```
Debian
  ↓
Kicksecure packages and hardening (upstream, unchanged)
  ↓
Dhampir branding and configuration (this repository)
  ↓
later: custom Dhampir kernel
  ↓
Dhampir.iso  and  Dhampir.ova
```

## Planned outputs

- **`Dhampir.iso`**: a bootable image you can write to a USB stick or boot in a VM.
- **`Dhampir.ova`**: a ready-to-import VirtualBox appliance.

Build outputs are **not** stored in Git. They will be published as GitHub Release assets. See [agents/BUILD.md](agents/BUILD.md) for how the builds work.

## Repository layout

| Path | What it holds |
|---|---|
| `derivative-maker` | The build program (inherited from upstream). |
| `branding/` | Names, colours and text used for the Dhampir identity. |
| `config/` | Build settings for Dhampir (overlay, not upstream edits). |
| `packages/dhampir-branding/` | A package with the visible Dhampir identity files. |
| `kernel/` | Placeholder for future kernel work. Empty for now. |
| `agents/` | Notes for AI coding agents and build reference, such as [agents/BUILD.md](agents/BUILD.md). See `AGENTS.md`. |

## Current status

**Phase 1 (in progress): setup and branding only.**

- [x] Repository structure defined.
- [ ] `dhampir-branding` package: started.
- [ ] Build settings for a `dhampir` flavor in `derivative-maker`.
- [ ] First `Dhampir.iso` built and tested.
- [ ] First `Dhampir.ova` built and tested.
- [ ] Custom kernel: **not started** and out of scope for Phase 1.

Nothing in this repository has been built into an ISO or OVA yet. Do not treat any statement here as tested unless it says so.

## Further reading

- [agents/BUILD.md](agents/BUILD.md): how the ISO and OVA builds work, in plain language.
- `README.mediawiki`: the upstream `derivative-maker` documentation.
- `AGENTS.md`: rules for contributors and AI agents.

## Licence

See [COPYING](COPYING). Upstream files keep their original licences.
