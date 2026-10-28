#!/bin/bash

## Copyright (C) 2026 potemkin666
## See the file COPYING for copying conditions.
## AI-Assisted

## Exercise the same isolated source-package boundary as the full builder.

set -o errexit
set -o nounset
set -o pipefail
set -o errtrace
shopt -s inherit_errexit
shopt -s shift_verbose
export LC_ALL=C

[ "${CI:-}" = true ]
package_repo_root="$(pwd -P)"
package_scratch="$(mktemp --directory --tmpdir="${RUNNER_TEMP}" dhampiros-package-check.XXXXXXXX)"
git -c safe.directory="${package_repo_root}" archive HEAD packages/dhampir | tar --extract --directory "${package_scratch}"
for package_name in dhampir-branding dhampir-meta-packages dhampiros-artwork dhampiros-motion; do
   cd -- "${package_scratch}/packages/dhampir/${package_name}"
   package_version="$(dpkg-parsechangelog --show-field Version)"
   package_upstream="${package_version%-*}"
   tar --create --xz --exclude=./debian --file="../${package_name}_${package_upstream}.orig.tar.xz" .
   dpkg-buildpackage --no-sign --build=full
   lintian --allow-root --fail-on error,warning "../${package_name}_${package_version}_amd64.changes"
   if [ "${package_name}" = dhampiros-artwork ]; then
      dpkg --install "../${package_name}_${package_version}_all.deb"
   fi
done
