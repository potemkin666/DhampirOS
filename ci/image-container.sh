#!/bin/bash

## Copyright (C) 2026 potemkin666
## See the file COPYING for copying conditions.
## AI-Assisted

## Never run the ref-updating official wrapper or enable the CI SMBIOS reader.

set -o errexit
set -o nounset
set -o pipefail
set -o errtrace
shopt -s inherit_errexit
shopt -s shift_verbose
export LC_ALL=C

[ "${CI:-}" = true ]
[ "$(dpkg --print-architecture)" = amd64 ]
case "${1:-}" in
   iso|virtualbox) image_target="${1}" ;;
   *) printf '%s\n' 'Unsupported image target.' >&2; exit 1 ;;
esac

export DEBFULLNAME='DhampirOS disposable candidate builder'
export DEBEMAIL='potemkin666@users.noreply.github.com'
export dist_build_target_arch=amd64
export dist_build_version=0.1.0-alpha.1
export dist_build_redistributable=true
export dist_build_sign_and_tag=true
export dist_build_smbios_reader=false
./help-steps/signing-key-create
./help-steps/sign-and-tag

./derivative-maker --flavor dhampir-lxqt --target "${image_target}" \
   --arch amd64 --freshness current --repo true --tb closed \
   --dry-run false --serial-console-enable false \
   --sanity-tests true
