use super::pipewire_stream::CameraError;
use pipewire as pw;
use pw::spa;
use spa::buffer::Data;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CapturePixelFormat {
    Yuy2,
    Uyvy,
    Rgb,
    Bgr,
    Rgba,
    Bgra,
}

impl From<CapturePixelFormat> for pw::spa::param::video::VideoFormat {
    fn from(format: CapturePixelFormat) -> Self {
        match format {
            CapturePixelFormat::Yuy2 => pw::spa::param::video::VideoFormat::YUY2,
            CapturePixelFormat::Uyvy => pw::spa::param::video::VideoFormat::UYVY,
            CapturePixelFormat::Rgb => pw::spa::param::video::VideoFormat::RGB,
            CapturePixelFormat::Bgr => pw::spa::param::video::VideoFormat::BGR,
            CapturePixelFormat::Rgba => pw::spa::param::video::VideoFormat::RGBA,
            CapturePixelFormat::Bgra => pw::spa::param::video::VideoFormat::BGRA,
        }
    }
}

impl TryFrom<pw::spa::param::video::VideoFormat> for CapturePixelFormat {
    type Error = CameraError;

    fn try_from(format: pw::spa::param::video::VideoFormat) -> Result<Self, Self::Error> {
        match format {
            pw::spa::param::video::VideoFormat::YUY2 => Ok(CapturePixelFormat::Yuy2),
            pw::spa::param::video::VideoFormat::UYVY => Ok(CapturePixelFormat::Uyvy),
            pw::spa::param::video::VideoFormat::RGB => Ok(CapturePixelFormat::Rgb),
            pw::spa::param::video::VideoFormat::BGR => Ok(CapturePixelFormat::Bgr),
            pw::spa::param::video::VideoFormat::RGBA => Ok(CapturePixelFormat::Rgba),
            pw::spa::param::video::VideoFormat::BGRA => Ok(CapturePixelFormat::Bgra),
            other => Err(CameraError::CaptureFailed(format!(
                "camera returned an unsupported pixel format: {other:?}"
            ))),
        }
    }
}

impl std::str::FromStr for CapturePixelFormat {
    type Err = CameraError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value.trim().to_ascii_uppercase().as_str() {
            "YUY2" => Ok(Self::Yuy2),
            "UYVY" => Ok(Self::Uyvy),
            "RGB" => Ok(Self::Rgb),
            "BGR" => Ok(Self::Bgr),
            "RGBA" => Ok(Self::Rgba),
            "BGRA" => Ok(Self::Bgra),
            other => Err(CameraError::Validation(format!(
                "unsupported pixel format: {other}"
            ))),
        }
    }
}

#[derive(Debug, Clone)]
pub struct CapturedFrame {
    pub pixels: Vec<u8>,
    pub width: u32,
    pub height: u32,
    pub stride: i32,
    pub pixel_format: CapturePixelFormat,
}

fn extract_frame_info(data: &mut Data) -> Result<(i32, &[u8]), CameraError> {
    let (chunk_offset, chunk_size, chunk_stride) = {
        let chunk = data.chunk();
        (chunk.offset(), chunk.size(), chunk.stride())
    };

    let offset = usize::try_from(chunk_offset).map_err(|_| {
        CameraError::CaptureFailed("camera returned invalid frame data".to_string())
    })?;
    let size = usize::try_from(chunk_size).map_err(|_| {
        CameraError::CaptureFailed("camera returned invalid frame data".to_string())
    })?;
    let bytes = data.data().ok_or_else(|| {
        CameraError::CaptureFailed("camera frame data was unavailable".to_string())
    })?;
    let end = offset.checked_add(size).ok_or_else(|| {
        CameraError::CaptureFailed("camera returned invalid frame data".to_string())
    })?;
    if end > bytes.len() {
        return Err(CameraError::CaptureFailed(
            "camera returned invalid frame data".to_string(),
        ));
    }

    Ok((chunk_stride, &bytes[offset..end]))
}

pub(super) fn build_captured_frame(
    data: &mut Data,
    width: u32,
    height: u32,
    pixel_format: CapturePixelFormat,
) -> Result<CapturedFrame, CameraError> {
    let (chunk_stride, frame_bytes) = extract_frame_info(data)?;

    Ok(CapturedFrame {
        pixels: frame_bytes.to_vec(),
        width,
        height,
        stride: chunk_stride,
        pixel_format,
    })
}
