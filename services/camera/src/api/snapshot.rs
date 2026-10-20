// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::api::parameters::{StreamFormat, StreamFormatFilter};
use crate::api::stream_format_collector::StreamFormatCollector;
use crate::camera::Camera;
use crate::helpers::is_camera_node;
use pipewire as pw;
use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::fmt;
use std::rc::Rc;
use std::time::Duration;
use tracing::warn;

const SNAPSHOT_TIMEOUT: Duration = Duration::from_secs(5);

#[cfg(feature = "smoke-test-failure-injection")]
const SNAPSHOT_FAILURE_INJECTION_ENV: &str = "CAIRN_CAMERA_SNAPSHOT_FAILURE";
#[cfg(feature = "smoke-test-failure-injection")]
const CAMERA_NODE_PARAMS_SYNC_FAILURE: &str = "camera-node-params-sync";

#[derive(Debug, PartialEq)]
pub enum SnapshotError {
    NotFound(u64),
    Unavailable(String),
}

impl std::fmt::Display for SnapshotError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFound(camera_id) => write!(f, "camera {camera_id} was not found"),
            Self::Unavailable(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for SnapshotError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct SnapshotCamera {
    pub(crate) object_serial: u64,
    pub(crate) name: String,
}

impl From<Camera> for SnapshotCamera {
    fn from(metadata: Camera) -> Self {
        Self {
            object_serial: metadata.object_serial,
            name: metadata.name,
        }
    }
}

pub(crate) fn list_cameras() -> Result<Vec<SnapshotCamera>, SnapshotError> {
    let PipeWireClient {
        mainloop,
        core,
        registry,
    } = create_pipewire_client()?;

    let state = Rc::new(RefCell::new(SnapshotState::default()));
    let registry_state = Rc::clone(&state);
    let remove_state = Rc::clone(&state);
    let _registry_listener = registry
        .add_listener_local()
        .global(move |global| {
            if !is_camera_node(global) {
                return;
            }
            append_camera(&mut registry_state.borrow_mut().cameras, global);
        })
        .global_remove(move |node_id| {
            remove_state.borrow_mut().cameras.remove(&node_id);
        })
        .register();

    run_until_synced(
        &mainloop,
        &core,
        "PipeWire snapshot timed out",
        SNAPSHOT_TIMEOUT,
    )?;
    Ok(state.borrow_mut().take_cameras())
}

pub(crate) fn list_camera_formats(
    camera_id: u64,
    filter: Option<StreamFormatFilter>,
) -> Result<(u64, Vec<StreamFormat>), SnapshotError> {
    let pipewire = create_pipewire_client()?;
    let selected_node: Rc<RefCell<Option<pw::node::Node>>> = Rc::new(RefCell::new(None));
    let listener_node = Rc::clone(&selected_node);
    let bind_error = Rc::new(RefCell::new(None));
    let listener_bind_error = Rc::clone(&bind_error);
    let bind_registry = pipewire.registry.clone();
    let _registry_listener = pipewire
        .registry
        .add_listener_local()
        .global(move |global| {
            if !is_camera_node(global) {
                return;
            }

            let Ok(camera) = Camera::try_from_global_object(global) else {
                return;
            };

            if camera.object_serial != camera_id {
                return;
            }

            let camera_node = match bind_registry.bind(global) {
                Ok(camera_node) => camera_node,
                Err(err) => {
                    *listener_bind_error.borrow_mut() = Some(err.to_string());
                    return;
                }
            };

            *listener_node.borrow_mut() = Some(camera_node);
        })
        .register();

    run_until_synced(
        &pipewire.mainloop,
        &pipewire.core,
        "PipeWire camera lookup timed out",
        SNAPSHOT_TIMEOUT,
    )?;

    let camera_node = selected_node.borrow_mut().take();
    let camera_node = match camera_node {
        Some(camera_node) => camera_node,
        None => {
            return Err(camera_lookup_error(
                camera_id,
                bind_error.borrow_mut().take(),
            ));
        }
    };

    let collector = StreamFormatCollector::new(camera_node, filter);

    collector.request_format_collection();

    run_until_synced(
        &pipewire.mainloop,
        &pipewire.core,
        "PipeWire format collection timed out",
        SNAPSHOT_TIMEOUT,
    )?;

    let formats = collector.take_collected_formats();

    Ok((camera_id, formats))
}

#[derive(Default)]
pub(super) struct SnapshotState {
    pub(super) cameras: HashMap<u32, SnapshotCamera>,
}

impl SnapshotState {
    pub(super) fn take_cameras(&mut self) -> Vec<SnapshotCamera> {
        let cameras = std::mem::take(&mut self.cameras);
        let mut cameras = cameras.into_values().collect::<Vec<_>>();
        cameras.sort_by_key(|camera| camera.object_serial);
        cameras
    }
}

struct PipeWireClient {
    mainloop: pw::main_loop::MainLoopRc,
    core: pw::core::CoreRc,
    registry: pw::registry::RegistryRc,
}

fn create_pipewire_client() -> Result<PipeWireClient, SnapshotError> {
    pw::init();

    let mainloop = pw::main_loop::MainLoopRc::new(None)
        .map_err(|err| unavailable(format!("failed to create PipeWire main loop: {err}")))?;
    let context = pw::context::ContextRc::new(&mainloop, None)
        .map_err(|err| unavailable(format!("failed to create PipeWire context: {err}")))?;
    let core = context
        .connect_rc(None)
        .map_err(|err| unavailable(format!("failed to connect to PipeWire: {err}")))?;
    let registry = core
        .get_registry_rc()
        .map_err(|err| unavailable(format!("failed to get PipeWire registry: {err}")))?;

    Ok(PipeWireClient {
        mainloop,
        core,
        registry,
    })
}

fn run_until_synced(
    mainloop: &pw::main_loop::MainLoopRc,
    core: &pw::core::CoreRc,
    timeout_message: &'static str,
    timeout: Duration,
) -> Result<(), SnapshotError> {
    #[cfg(feature = "smoke-test-failure-injection")]
    if timeout_message == "PipeWire format collection timed out"
        && std::env::var(SNAPSHOT_FAILURE_INJECTION_ENV).as_deref()
            == Ok(CAMERA_NODE_PARAMS_SYNC_FAILURE)
    {
        return Err(unavailable(
            "failed to sync PipeWire camera node params: injected smoke-test failure",
        ));
    }

    if timeout.is_zero() {
        return Err(unavailable(timeout_message));
    }
    let pending_sync = core
        .sync(0)
        .map_err(|err| unavailable(format!("failed to sync with PipeWire: {err}")))?;
    let complete = Rc::new(Cell::new(false));
    let done_complete = Rc::clone(&complete);
    let done_loop = mainloop.clone();
    let error = Rc::new(RefCell::new(None));
    let listener_error = Rc::clone(&error);
    let error_loop = mainloop.clone();
    let _core_listener = core
        .add_listener_local()
        .done(move |id, seq| {
            if is_pending_sync_complete(id, seq, pending_sync) {
                done_complete.set(true);
                done_loop.quit();
            }
        })
        .error(move |_id, _seq, _res, message| {
            *listener_error.borrow_mut() =
                Some(unavailable(format!("PipeWire core error: {message}")));
            error_loop.quit();
        })
        .register();

    let timeout_error = Rc::clone(&error);
    let timeout_complete = Rc::clone(&complete);
    let timeout_loop = mainloop.clone();
    let timeout_timer = mainloop.loop_().add_timer(move |_| {
        if timeout_complete.get() || timeout_error.borrow().is_some() {
            return;
        }
        *timeout_error.borrow_mut() = Some(unavailable(timeout_message));
        timeout_loop.quit();
    });
    timeout_timer
        .update_timer(Some(timeout), None)
        .into_result()
        .map_err(|err| unavailable(format!("failed to arm PipeWire snapshot timer: {err}")))?;

    mainloop.run();

    match error.borrow_mut().take() {
        Some(error) => Err(error),
        None if complete.get() => Ok(()),
        None => Err(unavailable("PipeWire snapshot did not complete")),
    }
}

pub(crate) fn append_camera<P>(
    cameras: &mut HashMap<u32, SnapshotCamera>,
    global: &pw::registry::GlobalObject<P>,
) where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
    let camera = match Camera::try_from_global_object(global) {
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
    cameras.insert(camera.node_id, SnapshotCamera::from(camera));
}

pub(crate) fn is_pending_sync_complete(
    id: u32,
    seq: pw::spa::utils::result::AsyncSeq,
    pending: pw::spa::utils::result::AsyncSeq,
) -> bool {
    id == pw::core::PW_ID_CORE && seq == pending
}

pub(super) fn camera_lookup_error(camera_id: u64, bind_error: Option<String>) -> SnapshotError {
    match bind_error {
        Some(err) => unavailable(format!(
            "failed to bind camera {camera_id} PipeWire node: {err}"
        )),
        None => SnapshotError::NotFound(camera_id),
    }
}

fn unavailable(message: impl Into<String>) -> SnapshotError {
    SnapshotError::Unavailable(message.into())
}
