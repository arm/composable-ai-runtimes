#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

# Check that Debian-provided licensing documentation survives into the final image.
set -eu

if ! command -v dpkg-query >/dev/null 2>&1; then
    printf 'No dpkg-query found; no APT inventory to validate.\n'
    exit 0
fi

packages=$(dpkg-query -W -f='${Package} ${db:Status-Status}\n')
count=0
while read -r package status; do
    [ "$status" = installed ] || continue
    copyright="/usr/share/doc/$package/copyright"
    if [ ! -f "$copyright" ] || [ ! -r "$copyright" ] || [ ! -s "$copyright" ]; then
        printf 'Missing copyright file for APT package %s: %s\n' "$package" "$copyright" >&2
        exit 1
    fi
    count=$((count + 1))
done <<EOF
$packages
EOF
if [ "$count" -eq 0 ]; then
    printf 'No installed APT packages; nothing to validate.\n'
    exit 0
fi

# Use dpkg's file records, rather than parsing free-form copyright prose.
shared=$(dpkg-query -S '/usr/share/common-licenses/*')
while IFS= read -r entry; do
    license=${entry#*: }
    [ -d "$license" ] && continue
    if [ ! -f "$license" ] || [ ! -r "$license" ] || [ ! -s "$license" ]; then
        printf 'Missing, empty, or unreadable shared license: %s\n' "$license" >&2
        exit 1
    fi
done <<EOF
$shared
EOF
printf 'APT packages checked: %s; recorded shared license files checked.\n' "$count"
