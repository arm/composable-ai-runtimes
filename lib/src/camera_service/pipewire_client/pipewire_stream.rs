use super::captured_frame::{CapturePixelFormat, CapturedFrame, build_captured_frame};
use pipewire as pw;
use pw::spa;
use spa::pod::Pod;
use std::cell::RefCell;
use std::rc::Rc;
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
pub struct CameraOptions {
    pub width: u32,
    pub height: u32,
    pub fps: u32,
    pub pixel_format: CapturePixelFormat,
}

impl Default for CameraOptions {
    fn default() -> Self {
        Self {
            width: 640,
            height: 480,
            fps: 30,
            pixel_format: CapturePixelFormat::Yuy2,
        }
    }
}

pub(crate) fn validate_camera_options(
    camera_id: u32,
    options: &CameraOptions,
) -> Result<(), CameraError> {
    if camera_id == 0 {
        return Err(CameraError::Validation(
            "camera_id must be non-zero".to_string(),
        ));
    }
    if options.width == 0 {
        return Err(CameraError::Validation(
            "width must be greater than zero".to_string(),
        ));
    }
    if options.height == 0 {
        return Err(CameraError::Validation(
            "height must be greater than zero".to_string(),
        ));
    }
    if options.fps == 0 {
        return Err(CameraError::Validation(
            "fps must be greater than zero".to_string(),
        ));
    }
    Ok(())
}

#[derive(Debug)]
pub enum CameraError {
    Validation(String),
    CaptureFailed(String),
}

impl std::fmt::Display for CameraError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Validation(message) => f.write_str(message),
            Self::CaptureFailed(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for CameraError {}

impl From<pw::Error> for CameraError {
    fn from(error: pw::Error) -> Self {
        Self::CaptureFailed(format!("failed to access camera: {error}"))
    }
}

#[derive(Clone, Copy)]
struct NegotiatedFormat {
    width: u32,
    height: u32,
    pixel_format: CapturePixelFormat,
}

struct FrameCaptureState {
    format: NegotiatedFormat,
    ready_frame: Option<CapturedFrame>,
    terminal_error: Option<CameraError>,
}

impl FrameCaptureState {
    fn new(options: &CameraOptions) -> Self {
        Self {
            format: NegotiatedFormat {
                width: options.width,
                height: options.height,
                pixel_format: options.pixel_format,
            },
            ready_frame: None,
            terminal_error: None,
        }
    }
}

fn capture_failure(message: impl Into<String>) -> CameraError {
    CameraError::CaptureFailed(message.into())
}

fn handle_stream_state_error(
    frame_capture_state: &Rc<RefCell<FrameCaptureState>>,
    new: pw::stream::StreamState,
    mainloop: &pw::main_loop::MainLoopRc,
) {
    if let pw::stream::StreamState::Error(message) = new {
        let error = if message.is_empty() {
            capture_failure("camera capture failed")
        } else {
            capture_failure(format!("camera capture failed: {message}"))
        };
        frame_capture_state
            .borrow_mut()
            .terminal_error
            .get_or_insert(error);
        mainloop.quit();
    }
}

fn handle_negotiated_format(
    frame_capture_state: &Rc<RefCell<FrameCaptureState>>,
    id: u32,
    param: Option<&Pod>,
) -> Result<(), CameraError> {
    let Some(param) = param else {
        return Ok(());
    };
    if id != pw::spa::param::ParamType::Format.as_raw() {
        return Ok(());
    }

    let Ok((media_type, media_subtype)) = pw::spa::param::format_utils::parse_format(param) else {
        return Ok(());
    };
    if media_type != pw::spa::param::format::MediaType::Video
        || media_subtype != pw::spa::param::format::MediaSubtype::Raw
    {
        return Ok(());
    }

    let mut format = pw::spa::param::video::VideoInfoRaw::default();
    if format.parse(param).is_err() {
        return Ok(());
    }

    let negotiated_pixel_format = CapturePixelFormat::try_from(format.format())?;

    frame_capture_state.borrow_mut().format = NegotiatedFormat {
        width: format.size().width,
        height: format.size().height,
        pixel_format: negotiated_pixel_format,
    };
    Ok(())
}

fn handle_stream_process(
    stream: &pw::stream::Stream,
    frame_capture_state: &Rc<RefCell<FrameCaptureState>>,
) -> Result<(), CameraError> {
    let Some(mut buffer) = stream.dequeue_buffer() else {
        return Ok(());
    };

    let [data] = buffer.datas_mut() else {
        return Err(capture_failure(
            "camera returned an unsupported frame layout",
        ));
    };

    let format = frame_capture_state.borrow().format;
    let frame = build_captured_frame(data, format.width, format.height, format.pixel_format)?;
    frame_capture_state.borrow_mut().ready_frame = Some(frame);
    Ok(())
}

pub(crate) fn capture_single_frame(
    camera_id: u32,
    options: &CameraOptions,
) -> Result<CapturedFrame, CameraError> {
    const POLL_INTERVAL: Duration = Duration::from_millis(100);
    const FRAME_TIMEOUT: Duration = Duration::from_secs(5);

    validate_camera_options(camera_id, options)?;

    pw::init();

    let mainloop = pw::main_loop::MainLoopRc::new(None)?;
    let context = pw::context::ContextRc::new(&mainloop, None)?;
    let core = context.connect_rc(None)?;

    let stream = pw::stream::StreamRc::new(
        core,
        "cairn-camera-capture",
        pw::properties::properties! {
            *pw::keys::MEDIA_TYPE => "Video",
            *pw::keys::MEDIA_CATEGORY => "Capture",
            *pw::keys::MEDIA_ROLE => "Camera",
            *pw::keys::NODE_DONT_RECONNECT => "true",
            *pw::keys::OBJECT_LINGER => "true",
        },
    )?;

    let format_param_obj = pw::spa::pod::object!(
        pw::spa::utils::SpaTypes::ObjectParamFormat,
        pw::spa::param::ParamType::EnumFormat,
        pw::spa::pod::property!(
            pw::spa::param::format::FormatProperties::MediaType,
            Id,
            pw::spa::param::format::MediaType::Video
        ),
        pw::spa::pod::property!(
            pw::spa::param::format::FormatProperties::MediaSubtype,
            Id,
            pw::spa::param::format::MediaSubtype::Raw
        ),
        pw::spa::pod::property!(
            pw::spa::param::format::FormatProperties::VideoFormat,
            Id,
            pw::spa::param::video::VideoFormat::from(options.pixel_format)
        ),
        pw::spa::pod::property!(
            pw::spa::param::format::FormatProperties::VideoSize,
            Rectangle,
            pw::spa::utils::Rectangle {
                width: options.width,
                height: options.height,
            }
        ),
        pw::spa::pod::property!(
            pw::spa::param::format::FormatProperties::VideoFramerate,
            Fraction,
            pw::spa::utils::Fraction {
                num: options.fps,
                denom: 1,
            }
        ),
    );

    let (buffer, _) = pw::spa::pod::serialize::PodSerializer::serialize(
        std::io::Cursor::new(Vec::new()),
        &pw::spa::pod::Value::Object(format_param_obj),
    )
    .map_err(|_| capture_failure("failed to start camera capture"))?;

    let values = buffer.into_inner();

    let mut params = [Pod::from_bytes(&values)
        .ok_or_else(|| capture_failure("failed to start camera capture"))?];

    stream.connect(
        spa::utils::Direction::Input,
        Some(camera_id),
        pw::stream::StreamFlags::AUTOCONNECT | pw::stream::StreamFlags::MAP_BUFFERS,
        &mut params,
    )?;

    let frame_capture_state = Rc::new(RefCell::new(FrameCaptureState::new(options)));
    let error_mainloop = mainloop.clone();
    let param_mainloop = mainloop.clone();
    let process_mainloop = mainloop.clone();

    let _listener = stream
        .add_local_listener_with_user_data(frame_capture_state.clone())
        .state_changed(move |_, frame_capture_state, _, new| {
            handle_stream_state_error(frame_capture_state, new, &error_mainloop);
        })
        .param_changed(move |_, frame_capture_state, id, param| {
            if let Err(error) = handle_negotiated_format(frame_capture_state, id, param) {
                frame_capture_state
                    .borrow_mut()
                    .terminal_error
                    .get_or_insert(error);
                param_mainloop.quit();
            }
        })
        .process(move |stream, frame_capture_state| {
            if let Err(error) = handle_stream_process(stream, frame_capture_state) {
                frame_capture_state
                    .borrow_mut()
                    .terminal_error
                    .get_or_insert(error);
            }
            process_mainloop.quit();
        })
        .register()
        .map_err(|_| capture_failure("failed to start camera capture"))?;

    let deadline = Instant::now() + FRAME_TIMEOUT;
    let loop_ref: &pw::loop_::Loop = mainloop.as_ref();

    loop {
        let mut frame_capture_state = frame_capture_state.borrow_mut();
        if let Some(frame) = frame_capture_state.ready_frame.take() {
            return Ok(frame);
        }
        if let Some(error) = frame_capture_state.terminal_error.take() {
            return Err(error);
        }
        drop(frame_capture_state);

        if Instant::now() >= deadline {
            return Err(capture_failure("timed out waiting for a camera frame"));
        }

        loop_ref.iterate(POLL_INTERVAL);
    }
}
