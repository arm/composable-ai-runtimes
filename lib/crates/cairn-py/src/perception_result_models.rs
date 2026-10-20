// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use cairn::perception_service::result as model;
use pyo3::types::{PyBytes, PyModule, PyModuleMethods};
use pyo3::{Bound, Py, PyResult, Python, pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};

/// Metadata shared by result objects.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "ObjectMetadata"
)]
#[derive(Clone)]
pub(super) struct PyObjectMetadata {
    /// Object identifier.
    id: u64,
    /// Parent object identifier.
    parent_id: u64,
    /// Object creation timestamp in nanoseconds.
    creation_timestamp_ns: u64,
}

impl From<model::ObjectMetadata> for PyObjectMetadata {
    fn from(value: model::ObjectMetadata) -> Self {
        let model::ObjectMetadata {
            id,
            parent_id,
            creation_timestamp_ns,
        } = value;

        Self {
            id,
            parent_id,
            creation_timestamp_ns,
        }
    }
}

/// Component identity attached to a result layer.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "ProducerInfo"
)]
#[derive(Clone)]
pub(super) struct PyProducerInfo {
    /// Producer instance identifier.
    instance_id: Option<String>,
    /// Producer component name.
    component: Option<String>,
    /// Producer implementation name.
    implementation: Option<String>,
}

impl From<model::ProducerInfo> for PyProducerInfo {
    fn from(value: model::ProducerInfo) -> Self {
        let model::ProducerInfo {
            instance_id,
            component,
            implementation,
        } = value;

        Self {
            instance_id,
            component,
            implementation,
        }
    }
}

/// Metadata describing the layer that produced a result.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "LayerInfo"
)]
#[derive(Clone)]
pub(super) struct PyLayerInfo {
    /// Inference engine name.
    engine: Option<String>,
    /// Model name.
    model: Option<String>,
    /// Producer-defined layer tags.
    tags: Option<String>,
    /// Identifier of the inference element.
    infer_element_id: Option<String>,
    /// Label family emitted by the model.
    label_family: Option<String>,
    /// Layer content type.
    content_type: Option<String>,
    /// Layer compositing mode.
    compositing_mode: Option<String>,
    /// Identity of the component that produced the layer.
    producer: Option<PyProducerInfo>,
}

impl From<model::LayerInfo> for PyLayerInfo {
    fn from(value: model::LayerInfo) -> Self {
        let model::LayerInfo {
            engine,
            model,
            tags,
            infer_element_id,
            label_family,
            content_type,
            compositing_mode,
            producer,
        } = value;

        Self {
            engine,
            model,
            tags,
            infer_element_id,
            label_family,
            content_type,
            compositing_mode,
            producer: producer.map(Into::into),
        }
    }
}

/// Axis-aligned bounding box.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "BoundingBox"
)]
#[derive(Clone)]
pub(super) struct PyBoundingBox {
    /// Horizontal coordinate.
    x: f32,
    /// Vertical coordinate.
    y: f32,
    /// Width.
    width: f32,
    /// Height.
    height: f32,
}

impl From<model::BoundingBox> for PyBoundingBox {
    fn from(value: model::BoundingBox) -> Self {
        let model::BoundingBox {
            x,
            y,
            width,
            height,
        } = value;

        Self {
            x,
            y,
            width,
            height,
        }
    }
}

/// Two-dimensional point.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "Point2d"
)]
#[derive(Clone)]
pub(super) struct PyPoint2d {
    /// Horizontal coordinate.
    x: f32,
    /// Vertical coordinate.
    y: f32,
}

impl From<model::Point2d> for PyPoint2d {
    fn from(value: model::Point2d) -> Self {
        let model::Point2d { x, y } = value;

        Self { x, y }
    }
}

/// Bitmap carried by a segmentation result.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    skip_from_py_object,
    module = "cairn.perception",
    name = "BitmapData"
)]
#[derive(Clone)]
pub(super) struct PyBitmapData {
    /// Width.
    width: u32,
    /// Height.
    height: u32,
    /// Element type used to encode the pixel data.
    value_type: Option<String>,
    /// Raw bitmap bytes.
    pixels: Option<Vec<u8>>,
}

impl From<model::BitmapData> for PyBitmapData {
    fn from(value: model::BitmapData) -> Self {
        let model::BitmapData {
            width,
            height,
            value_type,
            pixels,
        } = value;

        Self {
            width,
            height,
            value_type,
            pixels,
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl PyBitmapData {
    /// Bitmap width in pixels.
    #[getter]
    fn width(&self) -> u32 {
        self.width
    }

    /// Bitmap height in pixels.
    #[getter]
    fn height(&self) -> u32 {
        self.height
    }

    /// Element type used to encode the pixel data.
    #[getter]
    fn value_type(&self) -> Option<&str> {
        self.value_type.as_deref()
    }

    /// Raw bitmap bytes.
    #[getter]
    fn pixels(&self, py: Python<'_>) -> Option<Py<PyBytes>> {
        self.pixels
            .as_deref()
            .map(|pixels| PyBytes::new(py, pixels).unbind())
    }
}

/// One detected object.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "BoxDetection"
)]
#[derive(Clone)]
pub(super) struct PyBoxDetection {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Bounding box for the object.
    bounding_box: Option<PyBoundingBox>,
    /// Confidence score.
    confidence: f32,
    /// Numeric class identifier.
    class_id: i32,
    /// Human-readable class label.
    text: Option<String>,
}

impl From<model::BoxDetection> for PyBoxDetection {
    fn from(value: model::BoxDetection) -> Self {
        let model::BoxDetection {
            object,
            bounding_box,
            confidence,
            class_id,
            text,
        } = value;

        Self {
            object: object.map(Into::into),
            bounding_box: bounding_box.map(Into::into),
            confidence,
            class_id,
            text,
        }
    }
}

/// One object-detector payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "BoxDetections"
)]
#[derive(Clone)]
pub(super) struct PyBoxDetections {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Metadata for the layer that produced the payload.
    layer: Option<PyLayerInfo>,
    /// Detected objects.
    detections: Option<Vec<PyBoxDetection>>,
}

impl From<model::BoxDetections> for PyBoxDetections {
    fn from(value: model::BoxDetections) -> Self {
        let model::BoxDetections {
            schema_major,
            schema_minor,
            layer,
            detections,
        } = value;

        Self {
            schema_major,
            schema_minor,
            layer: layer.map(Into::into),
            detections: detections.map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// Candidate label for a classification.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "ClassificationCandidate"
)]
#[derive(Clone)]
pub(super) struct PyClassificationCandidate {
    /// Confidence score.
    confidence: f32,
    /// Numeric class identifier.
    class_id: i32,
    /// Human-readable class label.
    text: Option<String>,
    /// Horizontal coordinate.
    x: f32,
    /// Vertical coordinate.
    y: f32,
    /// Width.
    width: f32,
    /// Height.
    height: f32,
}

impl From<model::ClassificationCandidate> for PyClassificationCandidate {
    fn from(value: model::ClassificationCandidate) -> Self {
        let model::ClassificationCandidate {
            confidence,
            class_id,
            text,
            x,
            y,
            width,
            height,
        } = value;

        Self {
            confidence,
            class_id,
            text,
            x,
            y,
            width,
            height,
        }
    }
}

/// Classification candidates associated with one object.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "Classification"
)]
#[derive(Clone)]
pub(super) struct PyClassification {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Candidate classifications.
    candidates: Option<Vec<PyClassificationCandidate>>,
}

impl From<model::Classification> for PyClassification {
    fn from(value: model::Classification) -> Self {
        let model::Classification { object, candidates } = value;

        Self {
            object: object.map(Into::into),
            candidates: candidates.map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// Person-presence probabilities associated with one object.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "PersonPresence"
)]
#[derive(Clone)]
pub(super) struct PyPersonPresence {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Confidence that the object represents a person.
    yes_confidence: f32,
    /// Confidence that the object does not represent a person.
    no_confidence: f32,
}

impl From<model::PersonPresence> for PyPersonPresence {
    fn from(value: model::PersonPresence) -> Self {
        let model::PersonPresence {
            object,
            yes_confidence,
            no_confidence,
        } = value;

        Self {
            object: object.map(Into::into),
            yes_confidence,
            no_confidence,
        }
    }
}

/// One classification payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "Classifications"
)]
#[derive(Clone)]
pub(super) struct PyClassifications {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Metadata for the layer that produced the payload.
    layer: Option<PyLayerInfo>,
    /// Object classifications.
    classifications: Option<Vec<PyClassification>>,
    /// Person-presence classifications.
    person_presence: Option<Vec<PyPersonPresence>>,
}

impl From<model::Classifications> for PyClassifications {
    fn from(value: model::Classifications) -> Self {
        let model::Classifications {
            schema_major,
            schema_minor,
            layer,
            classifications,
            person_presence,
        } = value;

        Self {
            schema_major,
            schema_minor,
            layer: layer.map(Into::into),
            classifications: classifications
                .map(|nested| nested.into_iter().map(Into::into).collect()),
            person_presence: person_presence
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// Video geometry associated with an input frame.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "VideoFrameContext"
)]
#[derive(Clone)]
pub(super) struct PyVideoFrameContext {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Original frame width in pixels.
    original_width: u64,
    /// Original frame height in pixels.
    original_height: u64,
    /// Pixels cropped from the left edge of the source frame.
    source_crop_left: u64,
    /// Pixels cropped from the right edge of the source frame.
    source_crop_right: u64,
    /// Pixels cropped from the top edge of the source frame.
    source_crop_top: u64,
    /// Pixels cropped from the bottom edge of the source frame.
    source_crop_bottom: u64,
    /// Pixels added at the left edge during letterboxing.
    letterbox_left: u64,
    /// Pixels added at the right edge during letterboxing.
    letterbox_right: u64,
    /// Pixels added at the top edge during letterboxing.
    letterbox_top: u64,
    /// Pixels added at the bottom edge during letterboxing.
    letterbox_bottom: u64,
}

impl From<model::VideoFrameContext> for PyVideoFrameContext {
    fn from(value: model::VideoFrameContext) -> Self {
        let model::VideoFrameContext {
            object,
            original_width,
            original_height,
            source_crop_left,
            source_crop_right,
            source_crop_top,
            source_crop_bottom,
            letterbox_left,
            letterbox_right,
            letterbox_top,
            letterbox_bottom,
        } = value;

        Self {
            object: object.map(Into::into),
            original_width,
            original_height,
            source_crop_left,
            source_crop_right,
            source_crop_top,
            source_crop_bottom,
            letterbox_left,
            letterbox_right,
            letterbox_top,
            letterbox_bottom,
        }
    }
}

/// Audio geometry associated with an input frame.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "AudioFrameContext"
)]
#[derive(Clone)]
pub(super) struct PyAudioFrameContext {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Original audio channel count.
    original_channels: u64,
    /// Original audio sampling frequency.
    original_frequency: u64,
    /// Original audio sample count.
    original_sample_count: u64,
    /// Samples removed from the start of the audio.
    cut_left_sample_count: u64,
    /// Samples removed from the end of the audio.
    cut_right_sample_count: u64,
}

impl From<model::AudioFrameContext> for PyAudioFrameContext {
    fn from(value: model::AudioFrameContext) -> Self {
        let model::AudioFrameContext {
            object,
            original_channels,
            original_frequency,
            original_sample_count,
            cut_left_sample_count,
            cut_right_sample_count,
        } = value;

        Self {
            object: object.map(Into::into),
            original_channels,
            original_frequency,
            original_sample_count,
            cut_left_sample_count,
            cut_right_sample_count,
        }
    }
}

/// One frame-context payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "FrameContext"
)]
#[derive(Clone)]
pub(super) struct PyFrameContext {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Metadata for the layer that produced the payload.
    layer: Option<PyLayerInfo>,
    /// Video frame geometry.
    video: Option<PyVideoFrameContext>,
    /// Audio frame geometry.
    audio: Option<PyAudioFrameContext>,
}

impl From<model::FrameContext> for PyFrameContext {
    fn from(value: model::FrameContext) -> Self {
        let model::FrameContext {
            schema_major,
            schema_minor,
            layer,
            video,
            audio,
        } = value;

        Self {
            schema_major,
            schema_minor,
            layer: layer.map(Into::into),
            video: video.map(Into::into),
            audio: audio.map(Into::into),
        }
    }
}

/// Embedding vector associated with one object.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "ObjectEmbedding"
)]
#[derive(Clone)]
pub(super) struct PyObjectEmbedding {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Embedding vector values.
    values: Option<Vec<f32>>,
}

impl From<model::ObjectEmbedding> for PyObjectEmbedding {
    fn from(value: model::ObjectEmbedding) -> Self {
        let model::ObjectEmbedding { object, values } = value;

        Self {
            object: object.map(Into::into),
            values,
        }
    }
}

/// One object-embeddings payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "ObjectEmbeddings"
)]
#[derive(Clone)]
pub(super) struct PyObjectEmbeddings {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Metadata for the layer that produced the payload.
    layer: Option<PyLayerInfo>,
    /// Object embedding vectors.
    embeddings: Option<Vec<PyObjectEmbedding>>,
}

impl From<model::ObjectEmbeddings> for PyObjectEmbeddings {
    fn from(value: model::ObjectEmbeddings) -> Self {
        let model::ObjectEmbeddings {
            schema_major,
            schema_minor,
            layer,
            embeddings,
        } = value;

        Self {
            schema_major,
            schema_minor,
            layer: layer.map(Into::into),
            embeddings: embeddings.map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One tracked object.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "ObjectTrack"
)]
#[derive(Clone)]
pub(super) struct PyObjectTrack {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Identifier of the tracking source.
    source_id: u64,
    /// Tracked-object identifier.
    track_id: u64,
    /// Bounding box for the object.
    bounding_box: Option<PyBoundingBox>,
    /// Confidence score.
    confidence: f32,
    /// Numeric class identifier.
    class_id: i32,
    /// Human-readable class label.
    text: Option<String>,
    /// Optional tracker diagnostic.
    diagnostic: Option<String>,
    /// Whether the track is based only on prediction.
    predicted_only: bool,
}

impl From<model::ObjectTrack> for PyObjectTrack {
    fn from(value: model::ObjectTrack) -> Self {
        let model::ObjectTrack {
            object,
            source_id,
            track_id,
            bounding_box,
            confidence,
            class_id,
            text,
            diagnostic,
            predicted_only,
        } = value;

        Self {
            object: object.map(Into::into),
            source_id,
            track_id,
            bounding_box: bounding_box.map(Into::into),
            confidence,
            class_id,
            text,
            diagnostic,
            predicted_only,
        }
    }
}

/// One object-tracks payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "ObjectTracks"
)]
#[derive(Clone)]
pub(super) struct PyObjectTracks {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Metadata for the layer that produced the payload.
    layer: Option<PyLayerInfo>,
    /// Tracked objects.
    tracks: Option<Vec<PyObjectTrack>>,
}

impl From<model::ObjectTracks> for PyObjectTracks {
    fn from(value: model::ObjectTracks) -> Self {
        let model::ObjectTracks {
            schema_major,
            schema_minor,
            layer,
            tracks,
        } = value;

        Self {
            schema_major,
            schema_minor,
            layer: layer.map(Into::into),
            tracks: tracks.map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One performance-overlay payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "PerformanceOverlay"
)]
#[derive(Clone)]
pub(super) struct PyPerformanceOverlay {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Performance overlay text lines.
    lines: Option<Vec<String>>,
}

impl From<model::PerformanceOverlay> for PyPerformanceOverlay {
    fn from(value: model::PerformanceOverlay) -> Self {
        let model::PerformanceOverlay {
            schema_major,
            schema_minor,
            lines,
        } = value;

        Self {
            schema_major,
            schema_minor,
            lines,
        }
    }
}

/// One estimated object pose.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "PoseEstimation"
)]
#[derive(Clone)]
pub(super) struct PyPoseEstimation {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Confidence score.
    confidence: f32,
    /// Estimated yaw angle.
    yaw: f32,
    /// Estimated pitch angle.
    pitch: f32,
}

impl From<model::PoseEstimation> for PyPoseEstimation {
    fn from(value: model::PoseEstimation) -> Self {
        let model::PoseEstimation {
            object,
            confidence,
            yaw,
            pitch,
        } = value;

        Self {
            object: object.map(Into::into),
            confidence,
            yaw,
            pitch,
        }
    }
}

/// One pose-estimations payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "PoseEstimations"
)]
#[derive(Clone)]
pub(super) struct PyPoseEstimations {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Metadata for the layer that produced the payload.
    layer: Option<PyLayerInfo>,
    /// Estimated object poses.
    poses: Option<Vec<PyPoseEstimation>>,
}

impl From<model::PoseEstimations> for PyPoseEstimations {
    fn from(value: model::PoseEstimations) -> Self {
        let model::PoseEstimations {
            schema_major,
            schema_minor,
            layer,
            poses,
        } = value;

        Self {
            schema_major,
            schema_minor,
            layer: layer.map(Into::into),
            poses: poses.map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One object segmentation mask.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "SegmentationMask"
)]
#[derive(Clone)]
pub(super) struct PySegmentationMask {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Segmentation bitmap.
    bitmap: Option<PyBitmapData>,
}

impl From<model::SegmentationMask> for PySegmentationMask {
    fn from(value: model::SegmentationMask) -> Self {
        let model::SegmentationMask { object, bitmap } = value;

        Self {
            object: object.map(Into::into),
            bitmap: bitmap.map(Into::into),
        }
    }
}

/// One segmentation-masks payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "SegmentationMasks"
)]
#[derive(Clone)]
pub(super) struct PySegmentationMasks {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Metadata for the layer that produced the payload.
    layer: Option<PyLayerInfo>,
    /// Object segmentation masks.
    masks: Option<Vec<PySegmentationMask>>,
}

impl From<model::SegmentationMasks> for PySegmentationMasks {
    fn from(value: model::SegmentationMasks) -> Self {
        let model::SegmentationMasks {
            schema_major,
            schema_minor,
            layer,
            masks,
        } = value;

        Self {
            schema_major,
            schema_minor,
            layer: layer.map(Into::into),
            masks: masks.map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One tracked object's path.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "TrackTrace"
)]
#[derive(Clone)]
pub(super) struct PyTrackTrace {
    /// Metadata for the associated object.
    object: Option<PyObjectMetadata>,
    /// Tracked-object identifier.
    track_id: u64,
    /// Points in the tracked path.
    points: Option<Vec<PyPoint2d>>,
}

impl From<model::TrackTrace> for PyTrackTrace {
    fn from(value: model::TrackTrace) -> Self {
        let model::TrackTrace {
            object,
            track_id,
            points,
        } = value;

        Self {
            object: object.map(Into::into),
            track_id,
            points: points.map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One track-traces payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    skip_from_py_object,
    module = "cairn.perception",
    name = "TrackTraces"
)]
#[derive(Clone)]
pub(super) struct PyTrackTraces {
    /// Payload schema major version.
    schema_major: u16,
    /// Payload schema minor version.
    schema_minor: u16,
    /// Metadata for the layer that produced the payload.
    layer: Option<PyLayerInfo>,
    /// Tracked-object paths.
    traces: Option<Vec<PyTrackTrace>>,
}

impl From<model::TrackTraces> for PyTrackTraces {
    fn from(value: model::TrackTraces) -> Self {
        let model::TrackTraces {
            schema_major,
            schema_minor,
            layer,
            traces,
        } = value;

        Self {
            schema_major,
            schema_minor,
            layer: layer.map(Into::into),
            traces: traces.map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

pub(super) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyObjectMetadata>()?;
    module.add_class::<PyProducerInfo>()?;
    module.add_class::<PyLayerInfo>()?;
    module.add_class::<PyBoundingBox>()?;
    module.add_class::<PyPoint2d>()?;
    module.add_class::<PyBitmapData>()?;
    module.add_class::<PyBoxDetection>()?;
    module.add_class::<PyBoxDetections>()?;
    module.add_class::<PyClassificationCandidate>()?;
    module.add_class::<PyClassification>()?;
    module.add_class::<PyPersonPresence>()?;
    module.add_class::<PyClassifications>()?;
    module.add_class::<PyVideoFrameContext>()?;
    module.add_class::<PyAudioFrameContext>()?;
    module.add_class::<PyFrameContext>()?;
    module.add_class::<PyObjectEmbedding>()?;
    module.add_class::<PyObjectEmbeddings>()?;
    module.add_class::<PyObjectTrack>()?;
    module.add_class::<PyObjectTracks>()?;
    module.add_class::<PyPerformanceOverlay>()?;
    module.add_class::<PyPoseEstimation>()?;
    module.add_class::<PyPoseEstimations>()?;
    module.add_class::<PySegmentationMask>()?;
    module.add_class::<PySegmentationMasks>()?;
    module.add_class::<PyTrackTrace>()?;
    module.add_class::<PyTrackTraces>()?;
    Ok(())
}
