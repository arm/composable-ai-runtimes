use pipewire as pw;
use std::cell::RefCell;
use std::collections::HashMap;
use std::fmt;
use std::rc::Rc;
use std::time::Duration;

const SNAPSHOT_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, PartialEq, Eq)]
pub struct CameraMetadata {
    pub id: u32,
    pub name: String,
}

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

pub fn list_camera_metadata() -> Result<Vec<CameraMetadata>, SnapshotError> {
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
    let _registry_listener = registry
        .add_listener_local()
        .global(move |global| {
            append_camera_metadata(&mut registry_state.borrow_mut().cameras, global);
        })
        .global_remove(move |id| {
            remove_camera_metadata(&mut remove_state.borrow_mut().cameras, id);
        })
        .register();

    let pending = core
        .sync(0)
        .map_err(|err| unavailable(format!("failed to sync with PipeWire: {err}")))?;

    let done_state = Rc::clone(&state);
    let done_loop = mainloop.clone();
    let error_state = Rc::clone(&state);
    let error_loop = mainloop.clone();
    let timeout_state = Rc::clone(&state);
    let timeout_loop = mainloop.clone();
    let _core_listener = core
        .add_listener_local()
        .done(move |id, seq| {
            if is_pending_sync_complete(id, seq, pending) {
                done_state.borrow_mut().done = true;
                done_loop.quit();
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

    let mut state = state.borrow_mut();
    finish_snapshot(
        std::mem::take(&mut state.cameras),
        state.error.take(),
        state.done,
    )
}

#[derive(Default)]
pub(crate) struct SnapshotState {
    pub(crate) cameras: HashMap<u32, CameraMetadata>,
    pub(crate) done: bool,
    pub(crate) error: Option<SnapshotError>,
}

fn register_snapshot_timeout_timer<'a>(
    mainloop: &'a pw::main_loop::MainLoopRc,
    state: Rc<RefCell<SnapshotState>>,
    timeout_loop: pw::main_loop::MainLoopRc,
) -> Result<pw::loop_::TimerSource<'a>, SnapshotError> {
    let timeout_timer = mainloop.loop_().add_timer(move |_| {
        let mut state = state.borrow_mut();
        if !record_snapshot_timeout(&mut state) {
            return;
        }

        timeout_loop.quit();
    });
    timeout_timer
        .update_timer(Some(SNAPSHOT_TIMEOUT), None)
        .into_result()
        .map_err(|err| unavailable(format!("failed to arm PipeWire snapshot timer: {err}")))?;

    Ok(timeout_timer)
}

pub(crate) fn record_snapshot_timeout(state: &mut SnapshotState) -> bool {
    if state.done || state.error.is_some() {
        return false;
    }

    state.error = Some(unavailable("PipeWire snapshot timed out"));
    true
}

fn is_camera_node<P>(global: &pw::registry::GlobalObject<P>) -> bool
where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
    if global.type_ != pw::types::ObjectType::Node {
        return false;
    }

    global
        .props
        .as_ref()
        .is_some_and(|props| props.as_ref().get(&pw::keys::MEDIA_CLASS) == Some("Video/Source"))
}

fn camera_name<P>(global: &pw::registry::GlobalObject<P>) -> String
where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
    global
        .props
        .as_ref()
        .and_then(|props| {
            props
                .as_ref()
                .get(&pw::keys::NODE_NICK)
                .or_else(|| props.as_ref().get(&pw::keys::NODE_DESCRIPTION))
                .or_else(|| props.as_ref().get(&pw::keys::NODE_NAME))
        })
        .unwrap_or("")
        .to_string()
}

pub(crate) fn append_camera_metadata<P>(
    cameras: &mut HashMap<u32, CameraMetadata>,
    global: &pw::registry::GlobalObject<P>,
) where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
    if !is_camera_node(global) {
        return;
    }

    let id = global.id;
    cameras.insert(
        id,
        CameraMetadata {
            id,
            name: camera_name(global),
        },
    );
}

pub(crate) fn remove_camera_metadata(cameras: &mut HashMap<u32, CameraMetadata>, id: u32) {
    cameras.remove(&id);
}

pub(crate) fn is_pending_sync_complete(
    id: u32,
    seq: pw::spa::utils::result::AsyncSeq,
    pending: pw::spa::utils::result::AsyncSeq,
) -> bool {
    id == pw::core::PW_ID_CORE && seq == pending
}

pub(crate) fn finish_snapshot(
    cameras: HashMap<u32, CameraMetadata>,
    error: Option<SnapshotError>,
    done: bool,
) -> Result<Vec<CameraMetadata>, SnapshotError> {
    if let Some(error) = error {
        return Err(error);
    }

    if !done {
        return Err(unavailable("PipeWire snapshot did not complete"));
    }

    let mut cameras = cameras.into_values().collect::<Vec<_>>();
    cameras.sort_by_key(|camera| camera.id);
    Ok(cameras)
}

fn unavailable(message: impl Into<String>) -> SnapshotError {
    SnapshotError::Unavailable(message.into())
}
