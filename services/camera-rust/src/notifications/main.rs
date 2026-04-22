mod helpers;
#[cfg(test)]
mod helpers_test;

use std::error::Error;

use helpers::is_camera_node;
use pipewire::{self as pw, context::ContextRc, main_loop::MainLoopRc};

fn main() -> Result<(), Box<dyn Error>> {
    pw::init();
    let mainloop = MainLoopRc::new(None)?;
    let context = ContextRc::new(&mainloop, None)?;
    let core = context.connect_rc(None)?;
    let registry = core.get_registry_rc()?;

    let _listener = registry
        .add_listener_local()
        .global(|global| {
            if is_camera_node(global) {
                println!("{global:?}");
            }
        })
        .global_remove(|id| {
            println!("removed global id: {id}");
        })
        .register();

    mainloop.run();
    Ok(())
}
