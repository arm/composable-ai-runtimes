// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use chrono::{Datelike, Utc};
use pyo3_stub_gen::Result;
use std::fs;

fn main() -> Result<()> {
    let stub_info = _bindings::stub_info()?;
    stub_info.generate()?;
    let spdx_header = format!(
        "\
# SPDX-FileCopyrightText: Copyright {} Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

",
        Utc::now().year()
    );

    for module_name in stub_info.modules.keys() {
        let stub_path = stub_info
            .python_root
            .join(module_name.replace('.', "/"))
            .join("__init__.pyi");
        let generated_stub = fs::read_to_string(&stub_path)?;
        fs::write(stub_path, format!("{spdx_header}{generated_stub}"))?;
    }

    Ok(())
}
