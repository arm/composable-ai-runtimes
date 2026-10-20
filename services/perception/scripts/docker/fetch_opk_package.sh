#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

# Download and verify one OPK artifact.

set -eu

if [ "$#" -ne 3 ]; then
    echo "usage: $0 URL SHA256 DESTINATION" >&2
    exit 2
fi

package_url=$1
expected_sha256=$2
destination=$3

case "$package_url" in
    https://*) ;;
    *)
        echo "package URL must use HTTPS" >&2
        exit 2
        ;;
esac

if [ "${#expected_sha256}" -ne 64 ]; then
    echo "SHA256 must contain exactly 64 hexadecimal characters" >&2
    exit 2
fi
case "$expected_sha256" in
    *[!0-9A-Fa-f]*)
        echo "SHA256 must contain exactly 64 hexadecimal characters" >&2
        exit 2
        ;;
esac

destination_directory=$(dirname -- "$destination")
mkdir -p -- "$destination_directory"
temporary=$(mktemp "${destination}.partial.XXXXXX")
trap 'rm -f -- "$temporary"' EXIT HUP INT TERM

curl --fail --silent --show-error --location \
    --output "$temporary" \
    "$package_url"

if ! printf '%s  %s\n' "$expected_sha256" "$temporary" \
    | sha256sum --check --strict - >/dev/null; then
    echo "package checksum mismatch" >&2
    exit 1
fi

mv -- "$temporary" "$destination"
trap - EXIT HUP INT TERM
