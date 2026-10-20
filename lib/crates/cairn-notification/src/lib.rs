// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

#![warn(missing_docs)]
//! Asynchronous notification subscriptions.

#[cfg(test)]
use bytes::Bytes;
#[cfg(test)]
use prost::Message;

mod service;

mod messaging {
    include!("generated/cairn.messaging.v1.rs");
}

#[cfg(test)]
mod service_test;

pub use service::{
    Notification, NotificationService, NotificationServiceError, NotificationSubscription,
};

#[cfg(test)]
fn envelope(payload: impl AsRef<[u8]>) -> Vec<u8> {
    messaging::CairnEvent {
        payload: Bytes::copy_from_slice(payload.as_ref()),
        ..Default::default()
    }
    .encode_to_vec()
}
