use crate::camera_metadata::CameraMetadata;
use crate::helpers::is_camera_node;
use pipewire as pw;
use pw::spa::param::format::MediaSubtype;
use pw::spa::param::video::VideoFormat;
use std::cell::RefCell;
use std::collections::HashMap;
use std::fmt;
use std::rc::Rc;
use std::time::Duration;
use tracing::warn;

use super::camera_node_watch::CameraNodeWatch;

const SNAPSHOT_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, PartialEq)]
pub enum SnapshotError {
    Unavailable(String),
}

impl std::fmt::Display for SnapshotError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unavailable(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for SnapshotError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct SnapshotCamera {
    pub(crate) object_serial: u64,
    pub(crate) name: String,
    pub(crate) supported_formats: Vec<SnapshotSupportedFormat>,
}

impl From<CameraMetadata> for SnapshotCamera {
    fn from(metadata: CameraMetadata) -> Self {
        Self {
            object_serial: metadata.object_serial,
            name: metadata.name,
            supported_formats: vec![],
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum SnapshotSupportedFormat {
    RawVideo(VideoFormat),
    EncodedVideo(MediaSubtype),
}

impl SnapshotSupportedFormat {
    pub(super) fn sort_key(&self) -> String {
        self.to_string()
    }

    pub(super) fn has_same_name(&self, other: &Self) -> bool {
        self.sort_key() == other.sort_key()
    }
}

impl fmt::Display for SnapshotSupportedFormat {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::RawVideo(format) => f.write_str(&pipewire_variant_name(format)),
            Self::EncodedVideo(subtype) => f.write_str(&pipewire_variant_name(subtype)),
        }
    }
}

pub(crate) fn list_camera_metadata() -> Result<Vec<SnapshotCamera>, SnapshotError> {
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

    let state = Rc::new(RefCell::new(SnapshotState::default()));
    let registry_state = Rc::clone(&state);
    let remove_state = Rc::clone(&state);
    let bind_registry = registry.clone();
    let _registry_listener = registry
        .add_listener_local()
        .global(move |global| {
            let mut state = registry_state.borrow_mut();

            if !is_camera_node(global) {
                return;
            }

            if !matches!(state.phase, SnapshotPhase::Enumerating) {
                return;
            }


            let camera_node: pw::node::Node = match bind_registry.bind(global) {
                Ok(node) => node,
                Err(err) => {
                    warn!(
                        node_id = global.id,
                        error = %err,
                        "could not collect PipeWire camera node params; returning camera metadata without supported formats"
                    );
                    return;
                }
            };

            append_camera_metadata(&mut state.cameras, global);

            state
                .camera_node_watches
                .insert(global.id, CameraNodeWatch::new(global.id, camera_node));
        })
        .global_remove(move |node_id| {
            let mut state = remove_state.borrow_mut();
            state.cameras.remove(&node_id);
            state.camera_node_watches.remove(&node_id);
        })
        .register();

    // First pass: emit done event once all the camera enumerations have been processed.
    state.borrow_mut().pending_sync = Some(request_snapshot_sync(
        &core,
        "failed to sync with PipeWire",
    )?);

    let done_state = Rc::clone(&state);
    let done_loop = mainloop.clone();
    let sync_core = core.clone();
    let error_state = Rc::clone(&state);
    let error_loop = mainloop.clone();
    let timeout_state = Rc::clone(&state);
    let timeout_loop = mainloop.clone();
    let _core_listener =
        core.add_listener_local()
            .done(move |id, seq| {
                let mut state = done_state.borrow_mut();

                match state.phase {
                    SnapshotPhase::Enumerating => {
                        if state.pending_sync.is_some_and(|pending_sync| {
                            is_pending_sync_complete(id, seq, pending_sync)
                        }) {
                            state.request_camera_node_params();
                            // Second pass gate, will cause an event when all camera params are processed.
                            match request_snapshot_sync(
                                &sync_core,
                                "failed to sync PipeWire camera node params",
                            ) {
                                Ok(sync) => {
                                    state.pending_sync = Some(sync);
                                    state.phase = SnapshotPhase::CollectingParams;
                                }
                                Err(err) => {
                                    warn!(
                                        error = %err,
                                        "could not collect PipeWire camera node params; returning camera metadata without supported formats"
                                    );
                                    state.phase = SnapshotPhase::Complete;
                                    done_loop.quit();
                                }
                            }
                        }

                    }
                    SnapshotPhase::CollectingParams => {
                        if state.pending_sync.is_some_and(|pending_sync| {
                            is_pending_sync_complete(id, seq, pending_sync)
                        }) {
                            state.apply_collected_formats();
                            state.phase = SnapshotPhase::Complete;
                            done_loop.quit();
                        }
                    }
                    SnapshotPhase::Complete => {}
                }
            })
            .error(move |_id, _seq, _res, message| {
                error_state.borrow_mut().error =
                    Some(unavailable(format!("PipeWire core error: {message}")));
                error_loop.quit();
            })
            .register();

    let _timeout_timer = register_snapshot_timeout_timer(&mainloop, timeout_state, timeout_loop)?;

    mainloop.run();

    state.borrow_mut().take_result()
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) enum SnapshotPhase {
    Enumerating,
    CollectingParams,
    Complete,
}

pub(super) struct SnapshotState {
    pub(super) cameras: HashMap<u32, SnapshotCamera>,
    camera_node_watches: HashMap<u32, CameraNodeWatch>,
    pub(super) phase: SnapshotPhase,
    pub(super) error: Option<SnapshotError>,
    pending_sync: Option<pw::spa::utils::result::AsyncSeq>,
}

impl Default for SnapshotState {
    fn default() -> Self {
        Self {
            cameras: HashMap::new(),
            camera_node_watches: HashMap::new(),
            phase: SnapshotPhase::Enumerating,
            error: None,
            pending_sync: None,
        }
    }
}

impl SnapshotState {
    pub(super) fn is_pending_without_error(&self) -> bool {
        !matches!(self.phase, SnapshotPhase::Complete) && self.error.is_none()
    }

    pub(super) fn take_result(&mut self) -> Result<Vec<SnapshotCamera>, SnapshotError> {
        if let Some(error) = self.error.take() {
            return Err(error);
        }

        if !matches!(self.phase, SnapshotPhase::Complete) {
            return Err(unavailable("PipeWire snapshot did not complete"));
        }

        let cameras = std::mem::take(&mut self.cameras);
        let mut cameras = cameras.into_values().collect::<Vec<_>>();
        cameras.sort_by_key(|camera| camera.object_serial);
        Ok(cameras)
    }

    fn apply_collected_formats(&mut self) {
        let collected_formats = self
            .camera_node_watches
            .values()
            .map(|watch| (watch.node_id, watch.take_collected_formats()));

        apply_collected_formats_to_cameras(&mut self.cameras, collected_formats);
    }

    fn request_camera_node_params(&self) {
        for watch in self.camera_node_watches.values() {
            watch.request_format_collection();
        }
    }
}

pub(super) fn check_timeout_error(state: &SnapshotState) -> Option<SnapshotError> {
    if state.is_pending_without_error() {
        return Some(unavailable("PipeWire snapshot timed out"));
    }

    None
}

pub(super) fn apply_collected_formats_to_cameras(
    cameras: &mut HashMap<u32, SnapshotCamera>,
    collected_formats: impl IntoIterator<Item = (u32, Vec<SnapshotSupportedFormat>)>,
) {
    for (node_id, mut supported_formats) in collected_formats {
        let Some(camera) = cameras.get_mut(&node_id) else {
            continue;
        };

        supported_formats.sort_by_cached_key(SnapshotSupportedFormat::sort_key);
        supported_formats.dedup_by(|left, right| left.has_same_name(right));
        camera.supported_formats = supported_formats;
    }
}

fn request_snapshot_sync(
    sync_core: &pw::core::CoreRc,
    error_message: &'static str,
) -> Result<pw::spa::utils::result::AsyncSeq, SnapshotError> {
    sync_core
        .sync(0)
        .map_err(|err| unavailable(format!("{error_message}: {err}")))
}

fn register_snapshot_timeout_timer<'a>(
    mainloop: &'a pw::main_loop::MainLoopRc,
    state: Rc<RefCell<SnapshotState>>,
    timeout_loop: pw::main_loop::MainLoopRc,
) -> Result<pw::loop_::TimerSource<'a>, SnapshotError> {
    let timeout_timer = mainloop.loop_().add_timer(move |_| {
        let mut state = state.borrow_mut();
        let Some(error) = check_timeout_error(&state) else {
            return;
        };

        state.error = Some(error);
        timeout_loop.quit();
    });
    timeout_timer
        .update_timer(Some(SNAPSHOT_TIMEOUT), None)
        .into_result()
        .map_err(|err| unavailable(format!("failed to arm PipeWire snapshot timer: {err}")))?;

    Ok(timeout_timer)
}

pub(crate) fn append_camera_metadata<P>(
    cameras: &mut HashMap<u32, SnapshotCamera>,
    global: &pw::registry::GlobalObject<P>,
) where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
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
    cameras.insert(camera.node_id, SnapshotCamera::from(camera));
}

pub(crate) fn is_pending_sync_complete(
    id: u32,
    seq: pw::spa::utils::result::AsyncSeq,
    pending: pw::spa::utils::result::AsyncSeq,
) -> bool {
    id == pw::core::PW_ID_CORE && seq == pending
}

fn unavailable(message: impl Into<String>) -> SnapshotError {
    SnapshotError::Unavailable(message.into())
}

fn pipewire_variant_name(value: impl fmt::Debug) -> String {
    let debug = format!("{value:?}");
    match debug.rsplit_once("::") {
        Some((_, name)) => name.to_string(),
        None => debug,
    }
}
