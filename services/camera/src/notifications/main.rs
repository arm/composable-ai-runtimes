mod redis;
#[cfg(test)]
mod redis_contract_test;
#[cfg(test)]
mod redis_test;

use std::{cell::RefCell, collections::HashMap, error::Error, rc::Rc};

use crate::redis::{
    CameraEventType, RedisConfig, configure_redis_conn_with_retry, send_camera_event,
};
use camera::camera_metadata::CameraMetadata;
use camera::helpers::is_camera_node;
use camera::logging;
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

    let camera_cache = Rc::new(RefCell::new(HashMap::<u32, CameraMetadata>::new()));
    let camera_cache_remove = Rc::clone(&camera_cache);

    let _listener = registry
        .add_listener_local()
        .global(move |global| {
            if is_camera_node(global) {
                let camera = match CameraMetadata::try_from_global_object(global) {
                    Ok(camera) => camera,
                    Err(err) => {
                        warn!(
                            node_id = global.id,
                            error = %err,
                            "skipping camera node with invalid metadata"
                        );
                        return;
                    }
                };
                camera_cache
                    .borrow_mut()
                    .insert(camera.node_id, camera.clone());

                info!(
                    node_id = camera.node_id,
                    object_serial = camera.object_serial,
                    camera_name = %camera.name,
                    "camera connected"
                );

                publish_camera_event(
                    &redis_conn,
                    redis_config.as_ref(),
                    CameraEventType::Connected,
                    &camera,
                    events_channel.as_str(),
                );
            }
        })
        .global_remove(move |node_id| {
            let deleted_camera = { camera_cache_remove.borrow_mut().remove(&node_id) };

            if let Some(deleted_camera) = deleted_camera {
                info!(
                    node_id = deleted_camera.node_id,
                    object_serial = deleted_camera.object_serial,
                    camera_name = %deleted_camera.name,
                    "camera disconnected"
                );

                publish_camera_event(
                    &redis_conn_remove,
                    redis_config_remove.as_ref(),
                    CameraEventType::Disconnected,
                    &deleted_camera,
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

fn publish_camera_event(
    redis_conn: &Rc<RefCell<::redis::Connection>>,
    redis_config: &RedisConfig,
    event_type: CameraEventType,
    camera: &CameraMetadata,
    events_channel: &str,
) {
    let publish_result = send_camera_event(
        &mut redis_conn.borrow_mut(),
        event_type,
        camera,
        events_channel,
    );

    if let Err(err) = publish_result {
        let event_label = camera_event_label(event_type);
        warn!(
            node_id = camera.node_id,
            object_serial = camera.object_serial,
            camera_name = %camera.name,
            events_channel,
            error = %err,
            "failed to publish {event_label} camera notification"
        );

        reconnect_redis_client(redis_conn, redis_config);
    } else {
        let event_label = camera_event_label(event_type);
        info!(
            node_id = camera.node_id,
            object_serial = camera.object_serial,
            camera_name = %camera.name,
            events_channel,
            "published {event_label} camera notification"
        );
    }
}

fn camera_event_label(event_type: CameraEventType) -> &'static str {
    match event_type {
        CameraEventType::Connected => "connected",
        CameraEventType::Disconnected => "disconnected",
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
