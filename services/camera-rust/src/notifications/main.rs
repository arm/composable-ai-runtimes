use std::{cell::RefCell, collections::HashMap, error::Error, rc::Rc};

use camera_rust::camera_metadata::CameraMetadata;
use camera_rust::helpers::is_camera_node;
use camera_rust::redis::{
    CameraEventType, RedisConfig, configure_redis_conn_with_retry, send_camera_event,
};
use pipewire::{self as pw, context::ContextRc, main_loop::MainLoopRc};

fn main() -> Result<(), Box<dyn Error>> {
    let redis_config = RedisConfig::from_env();
    eprintln!(
        "connecting notifications Redis client to {}:{} and publishing camera events to {}",
        redis_config.host, redis_config.port, redis_config.events_channel
    );

    let redis_config = Rc::new(redis_config);
    let redis_conn = Rc::new(RefCell::new(configure_redis_conn_with_retry(
        redis_config.as_ref(),
    )?));
    let redis_conn_remove = Rc::clone(&redis_conn);
    let redis_config_remove = Rc::clone(&redis_config);
    let events_channel = redis_config.events_channel.clone();
    let events_channel_remove = events_channel.clone();

    eprintln!("connected notifications Redis client");

    pw::init();
    let mainloop = MainLoopRc::new(None)?;
    let context = ContextRc::new(&mainloop, None)?;
    let core = context.connect_rc(None)?;
    let registry = core.get_registry_rc()?;

    let camera_cache = Rc::new(RefCell::new(HashMap::<u32, CameraMetadata>::new()));
    let camera_cache_remove = Rc::clone(&camera_cache);

    let _listener = registry
        .add_listener_local()
        .global(move |global| {
            if is_camera_node(global) {
                let camera = CameraMetadata::from_global_object(global);
                camera_cache.borrow_mut().insert(camera.id, camera.clone());

                println!("added camera: {} - {}", camera.id, camera.name);

                publish_camera_event(
                    &redis_conn,
                    redis_config.as_ref(),
                    CameraEventType::Connected,
                    &camera,
                    events_channel.as_str(),
                );
            }
        })
        .global_remove(move |id| {
            let deleted_camera = { camera_cache_remove.borrow_mut().remove(&id) };

            if let Some(deleted_camera) = deleted_camera {
                println!(
                    "removed camera: {} - {}",
                    deleted_camera.id, deleted_camera.name
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

    mainloop.run();
    Ok(())
}

fn publish_camera_event(
    redis_conn: &Rc<RefCell<redis::Connection>>,
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
        eprintln!(
            "failed to publish {event_label} notification for {}: {err}",
            camera.id
        );

        reconnect_redis_client(redis_conn, redis_config);
    }
}

fn camera_event_label(event_type: CameraEventType) -> &'static str {
    match event_type {
        CameraEventType::Connected => "connected",
        CameraEventType::Disconnected => "disconnected",
    }
}

pub fn reconnect_redis_client(
    redis_conn: &Rc<RefCell<redis::Connection>>,
    redis_config: &RedisConfig,
) -> bool {
    match configure_redis_conn_with_retry(redis_config) {
        Ok(new_redis_conn) => {
            *redis_conn.borrow_mut() = new_redis_conn;
            eprintln!(
                "reconnected notifications Redis client to {}:{}",
                redis_config.host, redis_config.port
            );
            true
        }
        Err(reconnect_err) => {
            eprintln!(
                "failed to reconnect notifications Redis client to {}:{}: {reconnect_err}",
                redis_config.host, redis_config.port
            );
            false
        }
    }
}
