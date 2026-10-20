#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -eu

# Create the apt configuration locations used below.
mkdir -p \
  /usr/share/keyrings \
  /etc/apt/sources.list.d \
  /etc/apt/preferences.d \
  /etc/crypto-policies/back-ends

# Allow apt/gpg to read the Raspberry Pi repository metadata.
cat > /etc/crypto-policies/back-ends/apt-sequoia.config <<'EOF'
[hash_algorithms]
sha1.second_preimage_resistance = 2028-02-01
EOF

# Install the Raspberry Pi archive signing key.
curl -fsSL https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
  -o /tmp/raspberrypi.gpg.key
gpg --dearmor -o /usr/share/keyrings/raspberrypi-archive-keyring.gpg \
  /tmp/raspberrypi.gpg.key
rm -f /tmp/raspberrypi.gpg.key

# Add the Raspberry Pi package repository.
cat > /etc/apt/sources.list.d/raspberrypi.list <<'EOF'
deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] https://archive.raspberrypi.com/debian trixie main
EOF

# Prefer Raspberry Pi camera packages without replacing unrelated Debian packages.
cat > /etc/apt/preferences.d/raspberrypi-camera <<'EOF'
Package: *
Pin: release o=Raspberry Pi Foundation,n=trixie
Pin-Priority: 100

Package: libcamera* libpisp* pipewire* libpipewire-* libspa-*
Pin: release o=Raspberry Pi Foundation,n=trixie
Pin-Priority: 700
EOF
