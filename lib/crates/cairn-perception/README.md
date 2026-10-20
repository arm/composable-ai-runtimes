<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# arm-cairn-perception

`arm-cairn-perception` is an internal sub-crate of Cairn.

**Important Note**: This crate is not intended for external usage. Please refer to the main
`arm-cairn` crate for intended usage.

Regenerate the checked-in Perception gRPC bindings after changing the service proto:

```bash
cd lib
cargo run --locked -p arm-cairn-perception --example generate_perception_proto
```
