// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

mod config;
mod parameters;
mod server;
mod service;
mod snapshot;
mod stream_format_collector;

#[cfg(test)]
mod contract_tests;

pub use server::api_listen_addr;
pub use server::serve;

#[cfg(test)]
mod config_test;
#[cfg(test)]
mod parameters_test;
#[cfg(test)]
mod service_test;
#[cfg(test)]
mod snapshot_test;
