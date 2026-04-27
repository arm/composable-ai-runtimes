mod helpers;
#[cfg(test)]
mod helpers_test;

use std::{cell::RefCell, collections::HashMap, error::Error, rc::Rc};

use helpers::is_camera_node;
use pipewire::{self as pw, context::ContextRc, main_loop::MainLoopRc};

#[derive(Debug)]
struct CameraMetadata {
    id: u32,
    name: String,
}

fn main() -> Result<(), Box<dyn Error>> {
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
                println!("{global:?}");
                let camera = CameraMetadata {
                    id: global.id,
                    name: global
                        .props
                        .and_then(|props| props.get("node.nick").map(|s| s.to_string()))
                        .unwrap_or_else(|| "unknown".to_string()),
                };

                camera_cache.borrow_mut().insert(global.id, camera);
            }
        })
        .global_remove(move |id| {
            let deleted_camera = { camera_cache_remove.borrow_mut().remove(&id) };

            if let Some(deleted_camera) = deleted_camera {
                println!(
                    "removed camera: {} - {}",
                    deleted_camera.id, deleted_camera.name
                );
            }
        })
        .register();

    mainloop.run();
    Ok(())
}
