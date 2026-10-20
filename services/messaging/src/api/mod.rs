// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

mod config;
mod health;
mod server;

pub use server::{api_listen_addr, serve};

#[cfg(test)]
mod config_test;

#[cfg(test)]
mod health_test;
