// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

mod redis;
#[cfg(test)]
mod redis_contract_test;
#[cfg(test)]
mod redis_test;
mod messaging {
    include!("generated/cairn.messaging.v01.rs");
}

use std::{cell::RefCell, collections::HashMap, error::Error, rc::Rc};

use crate::redis::{
    DeviceEventType, RedisConfig, configure_redis_conn_with_retry, send_device_event,
};
use media::device::{Device, DeviceType};
use media::helpers::is_device_type;
use media::logging;
use pipewire::{self as pw, context::ContextRc, main_loop::MainLoopRc};
use tracing::{debug, info, warn};

fn main() -> Result<(), Box<dyn Error>> {
    logging::init();

    let redis_config = RedisConfig::from_env();
    info!(
        redis_host = %redis_config.host,
        redis_port = %redis_config.port,
        events_channel = %redis_config.events_channel,
        "connecting notifications Redis client"
    );

    let redis_config = Rc::new(redis_config);
    let redis_conn = Rc::new(RefCell::new(configure_redis_conn_with_retry(
        redis_config.as_ref(),
    )?));
    let redis_conn_remove = Rc::clone(&redis_conn);
    let redis_config_remove = Rc::clone(&redis_config);
    let events_channel = redis_config.events_channel.clone();
    let events_channel_remove = events_channel.clone();

    info!("connected notifications Redis client");

    pw::init();
    debug!("initialized PipeWire");

    let mainloop = MainLoopRc::new(None)?;
    debug!("created PipeWire main loop");

    let context = ContextRc::new(&mainloop, None)?;
    debug!("created PipeWire context");

    let core = context.connect_rc(None)?;
    debug!("connected PipeWire core");

    let registry = core.get_registry_rc()?;
    debug!("acquired PipeWire registry");

    let device_cache = Rc::new(RefCell::new(HashMap::<u32, Device>::new()));
    let device_cache_remove = Rc::clone(&device_cache);

    let _listener = registry
        .add_listener_local()
        .global(move |global| {
            if is_device_type(global, &DeviceType::Camera)
                || is_device_type(global, &DeviceType::Microphone)
            {
                let device = match Device::try_from_global_object(global) {
                    Ok(device) => device,
                    Err(err) => {
                        warn!(
                            node_id = global.id,
                            error = %err,
                            "skipping device node with invalid metadata"
                        );
                        return;
                    }
                };
                device_cache.borrow_mut().insert(global.id, device.clone());

                info!(
                    node_id = device.node_id,
                    object_serial = device.object_serial,
                    device_type = ?device.device_type,
                    device_name = %device.name,
                    "device connected"
                );

                publish_device_event(
                    &redis_conn,
                    redis_config.as_ref(),
                    DeviceEventType::Connected,
                    &device,
                    events_channel.as_str(),
                );
            }
        })
        .global_remove(move |node_id| {
            let deleted_device = { device_cache_remove.borrow_mut().remove(&node_id) };

            if let Some(deleted_device) = deleted_device {
                info!(
                    node_id = deleted_device.node_id,
                    object_serial = deleted_device.object_serial,
                    device_type = ?deleted_device.device_type,
                    device_name = %deleted_device.name,
                    "device disconnected"
                );

                publish_device_event(
                    &redis_conn_remove,
                    redis_config_remove.as_ref(),
                    DeviceEventType::Disconnected,
                    &deleted_device,
                    events_channel_remove.as_str(),
                );
            }
        })
        .register();

    debug!("registered PipeWire registry listener");
    mainloop.run();
    debug!("PipeWire main loop returned");
    Ok(())
}

fn publish_device_event(
    redis_conn: &Rc<RefCell<::redis::Connection>>,
    redis_config: &RedisConfig,
    event_type: DeviceEventType,
    device: &Device,
    events_channel: &str,
) {
    let publish_result = send_device_event(
        &mut redis_conn.borrow_mut(),
        event_type,
        device,
        events_channel,
    );

    if let Err(err) = publish_result {
        let event_label = device_event_label(event_type);
        warn!(
            node_id = device.node_id,
            object_serial = device.object_serial,
            device_type = ?device.device_type,
            device_name = %device.name,
            events_channel,
            error = %err,
            "failed to publish {event_label} device event"
        );

        reconnect_redis_client(redis_conn, redis_config);
    } else {
        let event_label = device_event_label(event_type);
        info!(
            node_id = device.node_id,
            object_serial = device.object_serial,
            device_type = ?device.device_type,
            device_name = %device.name,
            events_channel,
            "published {event_label} device event"
        );
    }
}

fn device_event_label(event_type: DeviceEventType) -> &'static str {
    match event_type {
        DeviceEventType::Connected => "connected",
        DeviceEventType::Disconnected => "disconnected",
    }
}

pub fn reconnect_redis_client(
    redis_conn: &Rc<RefCell<::redis::Connection>>,
    redis_config: &RedisConfig,
) -> bool {
    info!(
        redis_host = %redis_config.host,
        redis_port = %redis_config.port,
        "reconnecting notifications Redis client"
    );

    match configure_redis_conn_with_retry(redis_config) {
        Ok(new_redis_conn) => {
            *redis_conn.borrow_mut() = new_redis_conn;
            info!(
                redis_host = %redis_config.host,
                redis_port = %redis_config.port,
                "reconnected notifications Redis client"
            );
            true
        }
        Err(reconnect_err) => {
            warn!(
                redis_host = %redis_config.host,
                redis_port = %redis_config.port,
                error = %reconnect_err,
                "failed to reconnect notifications Redis client"
            );
            false
        }
    }
}
