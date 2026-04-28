use std::{cell::RefCell, collections::HashMap, error::Error, rc::Rc};

use camera_rust::camera_metadata::CameraMetadata;
use camera_rust::helpers::is_camera_node;
use camera_rust::redis::{CameraEventType, RedisConfig, configure_redis_conn, send_camera_event};
use pipewire::{self as pw, context::ContextRc, main_loop::MainLoopRc};

fn main() -> Result<(), Box<dyn Error>> {
    let redis_config = RedisConfig::from_env();
    eprintln!(
        "connecting notifications Redis client to {}:{} and publishing camera events to {}",
        redis_config.host, redis_config.port, redis_config.events_channel
    );

    let redis_conn = Rc::new(RefCell::new(configure_redis_conn(&redis_config)?));
    let redis_conn_remove = Rc::clone(&redis_conn);
    let events_channel = redis_config.events_channel;
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

                if let Err(err) = send_camera_event(
                    &mut redis_conn.borrow_mut(),
                    CameraEventType::Connected,
                    &camera,
                    events_channel.as_str(),
                ) {
                    eprintln!(
                        "failed to publish connected notification for {}: {err}",
                        camera.id
                    );
                }
            }
        })
        .global_remove(move |id| {
            let deleted_camera = { camera_cache_remove.borrow_mut().remove(&id) };

            if let Some(deleted_camera) = deleted_camera {
                println!(
                    "removed camera: {} - {}",
                    deleted_camera.id, deleted_camera.name
                );

                if let Err(err) = send_camera_event(
                    &mut redis_conn_remove.borrow_mut(),
                    CameraEventType::Disconnected,
                    &deleted_camera,
                    events_channel_remove.as_str(),
                ) {
                    eprintln!(
                        "failed to publish disconnected notification for {}: {err}",
                        deleted_camera.id
                    );
                }
            }
        })
        .register();

    mainloop.run();
    Ok(())
}
