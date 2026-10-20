// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use open_perception_kit::fb::open_perception_kit::metadata as opk;

/// Metadata shared by result objects.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct ObjectMetadata {
    pub id: u64,
    pub parent_id: u64,
    pub creation_timestamp_ns: u64,
}

impl From<opk::ObjectMetaT> for ObjectMetadata {
    fn from(value: opk::ObjectMetaT) -> Self {
        Self {
            id: value.id,
            parent_id: value.parent_id,
            creation_timestamp_ns: value.creation_ts_ns,
        }
    }
}

/// Component identity attached to a result layer.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct ProducerInfo {
    pub instance_id: Option<String>,
    pub component: Option<String>,
    pub implementation: Option<String>,
}

impl From<opk::ProducerInfoT> for ProducerInfo {
    fn from(value: opk::ProducerInfoT) -> Self {
        Self {
            instance_id: value.instance_id,
            component: value.component,
            implementation: value.implementation,
        }
    }
}

/// Metadata describing the layer that produced a result.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct LayerInfo {
    pub engine: Option<String>,
    pub model: Option<String>,
    pub tags: Option<String>,
    pub infer_element_id: Option<String>,
    pub label_family: Option<String>,
    pub content_type: Option<String>,
    pub compositing_mode: Option<String>,
    pub producer: Option<ProducerInfo>,
}

impl From<opk::LayerInfoT> for LayerInfo {
    fn from(value: opk::LayerInfoT) -> Self {
        Self {
            engine: value.engine,
            model: value.model,
            tags: value.tags,
            infer_element_id: value.infer_element_id,
            label_family: value.label_family,
            content_type: value.content_type,
            compositing_mode: value.compositing_mode,
            producer: value.producer.map(|nested| (*nested).into()),
        }
    }
}

/// Axis-aligned bounding box.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct BoundingBox {
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
}

impl From<opk::BoundingBoxT> for BoundingBox {
    fn from(value: opk::BoundingBoxT) -> Self {
        Self {
            x: value.x,
            y: value.y,
            width: value.width,
            height: value.height,
        }
    }
}

/// Two-dimensional point.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct Point2d {
    pub x: f32,
    pub y: f32,
}

impl From<opk::Point2fT> for Point2d {
    fn from(value: opk::Point2fT) -> Self {
        Self {
            x: value.x,
            y: value.y,
        }
    }
}

/// Bitmap carried by a segmentation result.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct BitmapData {
    pub width: u32,
    pub height: u32,
    pub value_type: Option<String>,
    pub pixels: Option<Vec<u8>>,
}

impl From<opk::BitmapDataT> for BitmapData {
    fn from(value: opk::BitmapDataT) -> Self {
        Self {
            width: value.width,
            height: value.height,
            value_type: value.value_type,
            pixels: value.pixels,
        }
    }
}

/// One detected object.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct BoxDetection {
    pub object: Option<ObjectMetadata>,
    pub bounding_box: Option<BoundingBox>,
    pub confidence: f32,
    pub class_id: i32,
    pub text: Option<String>,
}

impl From<opk::BoxDetectionT> for BoxDetection {
    fn from(value: opk::BoxDetectionT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            bounding_box: value.box_.map(|nested| (*nested).into()),
            confidence: value.confidence,
            class_id: value.class_id,
            text: value.text,
        }
    }
}

/// One object-detector payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct BoxDetections {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub layer: Option<LayerInfo>,
    pub detections: Option<Vec<BoxDetection>>,
}

impl From<opk::BoxDetectionsT> for BoxDetections {
    fn from(value: opk::BoxDetectionsT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            layer: value.layer.map(|nested| (*nested).into()),
            detections: value
                .detections
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// Candidate label for a classification.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct ClassificationCandidate {
    pub confidence: f32,
    pub class_id: i32,
    pub text: Option<String>,
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
}

impl From<opk::ClassificationCandidateT> for ClassificationCandidate {
    fn from(value: opk::ClassificationCandidateT) -> Self {
        Self {
            confidence: value.confidence,
            class_id: value.class_id,
            text: value.text,
            x: value.x,
            y: value.y,
            width: value.w,
            height: value.h,
        }
    }
}

/// Classification candidates associated with one object.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct Classification {
    pub object: Option<ObjectMetadata>,
    pub candidates: Option<Vec<ClassificationCandidate>>,
}

impl From<opk::ClassificationT> for Classification {
    fn from(value: opk::ClassificationT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            candidates: value
                .candidates
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// Person-presence probabilities associated with one object.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct PersonPresence {
    pub object: Option<ObjectMetadata>,
    pub yes_confidence: f32,
    pub no_confidence: f32,
}

impl From<opk::PersonPresenceT> for PersonPresence {
    fn from(value: opk::PersonPresenceT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            yes_confidence: value.yes_confidence,
            no_confidence: value.no_confidence,
        }
    }
}

/// One classification payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct Classifications {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub layer: Option<LayerInfo>,
    pub classifications: Option<Vec<Classification>>,
    pub person_presence: Option<Vec<PersonPresence>>,
}

impl From<opk::ClassificationsT> for Classifications {
    fn from(value: opk::ClassificationsT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            layer: value.layer.map(|nested| (*nested).into()),
            classifications: value
                .classifications
                .map(|nested| nested.into_iter().map(Into::into).collect()),
            person_presence: value
                .person_presence
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// Video geometry associated with an input frame.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct VideoFrameContext {
    pub object: Option<ObjectMetadata>,
    pub original_width: u64,
    pub original_height: u64,
    pub source_crop_left: u64,
    pub source_crop_right: u64,
    pub source_crop_top: u64,
    pub source_crop_bottom: u64,
    pub letterbox_left: u64,
    pub letterbox_right: u64,
    pub letterbox_top: u64,
    pub letterbox_bottom: u64,
}

impl From<opk::VideoFrameContextT> for VideoFrameContext {
    fn from(value: opk::VideoFrameContextT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            original_width: value.original_width,
            original_height: value.original_height,
            source_crop_left: value.source_crop_left,
            source_crop_right: value.source_crop_right,
            source_crop_top: value.source_crop_top,
            source_crop_bottom: value.source_crop_bottom,
            letterbox_left: value.letterbox_left,
            letterbox_right: value.letterbox_right,
            letterbox_top: value.letterbox_top,
            letterbox_bottom: value.letterbox_bottom,
        }
    }
}

/// Audio geometry associated with an input frame.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct AudioFrameContext {
    pub object: Option<ObjectMetadata>,
    pub original_channels: u64,
    pub original_frequency: u64,
    pub original_sample_count: u64,
    pub cut_left_sample_count: u64,
    pub cut_right_sample_count: u64,
}

impl From<opk::AudioFrameContextT> for AudioFrameContext {
    fn from(value: opk::AudioFrameContextT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            original_channels: value.original_channels,
            original_frequency: value.original_frequency,
            original_sample_count: value.original_sample_count,
            cut_left_sample_count: value.cut_left_sample_count,
            cut_right_sample_count: value.cut_right_sample_count,
        }
    }
}

/// One frame-context payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct FrameContext {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub layer: Option<LayerInfo>,
    pub video: Option<VideoFrameContext>,
    pub audio: Option<AudioFrameContext>,
}

impl From<opk::FrameContextT> for FrameContext {
    fn from(value: opk::FrameContextT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            layer: value.layer.map(|nested| (*nested).into()),
            video: value.video.map(|nested| (*nested).into()),
            audio: value.audio.map(|nested| (*nested).into()),
        }
    }
}

/// Embedding vector associated with one object.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct ObjectEmbedding {
    pub object: Option<ObjectMetadata>,
    pub values: Option<Vec<f32>>,
}

impl From<opk::ObjectEmbeddingT> for ObjectEmbedding {
    fn from(value: opk::ObjectEmbeddingT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            values: value.values,
        }
    }
}

/// One object-embeddings payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct ObjectEmbeddings {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub layer: Option<LayerInfo>,
    pub embeddings: Option<Vec<ObjectEmbedding>>,
}

impl From<opk::ObjectEmbeddingsT> for ObjectEmbeddings {
    fn from(value: opk::ObjectEmbeddingsT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            layer: value.layer.map(|nested| (*nested).into()),
            embeddings: value
                .embeddings
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One tracked object.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct ObjectTrack {
    pub object: Option<ObjectMetadata>,
    pub source_id: u64,
    pub track_id: u64,
    pub bounding_box: Option<BoundingBox>,
    pub confidence: f32,
    pub class_id: i32,
    pub text: Option<String>,
    pub diagnostic: Option<String>,
    pub predicted_only: bool,
}

impl From<opk::ObjectTrackT> for ObjectTrack {
    fn from(value: opk::ObjectTrackT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            source_id: value.source_id,
            track_id: value.track_id,
            bounding_box: value.box_.map(|nested| (*nested).into()),
            confidence: value.confidence,
            class_id: value.class_id,
            text: value.text,
            diagnostic: value.diagnostic,
            predicted_only: value.predicted_only,
        }
    }
}

/// One object-tracks payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct ObjectTracks {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub layer: Option<LayerInfo>,
    pub tracks: Option<Vec<ObjectTrack>>,
}

impl From<opk::ObjectTracksT> for ObjectTracks {
    fn from(value: opk::ObjectTracksT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            layer: value.layer.map(|nested| (*nested).into()),
            tracks: value
                .tracks
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One performance-overlay payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct PerformanceOverlay {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub lines: Option<Vec<String>>,
}

impl From<opk::PerformanceOverlayT> for PerformanceOverlay {
    fn from(value: opk::PerformanceOverlayT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            lines: value.lines,
        }
    }
}

/// One estimated object pose.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct PoseEstimation {
    pub object: Option<ObjectMetadata>,
    pub confidence: f32,
    pub yaw: f32,
    pub pitch: f32,
}

impl From<opk::PoseEstimationT> for PoseEstimation {
    fn from(value: opk::PoseEstimationT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            confidence: value.confidence,
            yaw: value.yaw,
            pitch: value.pitch,
        }
    }
}

/// One pose-estimations payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct PoseEstimations {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub layer: Option<LayerInfo>,
    pub poses: Option<Vec<PoseEstimation>>,
}

impl From<opk::PoseEstimationsT> for PoseEstimations {
    fn from(value: opk::PoseEstimationsT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            layer: value.layer.map(|nested| (*nested).into()),
            poses: value
                .poses
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One object segmentation mask.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct SegmentationMask {
    pub object: Option<ObjectMetadata>,
    pub bitmap: Option<BitmapData>,
}

impl From<opk::SegmentationMaskT> for SegmentationMask {
    fn from(value: opk::SegmentationMaskT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            bitmap: value.bitmap.map(|nested| (*nested).into()),
        }
    }
}

/// One segmentation-masks payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct SegmentationMasks {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub layer: Option<LayerInfo>,
    pub masks: Option<Vec<SegmentationMask>>,
}

impl From<opk::SegmentationMasksT> for SegmentationMasks {
    fn from(value: opk::SegmentationMasksT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            layer: value.layer.map(|nested| (*nested).into()),
            masks: value
                .masks
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One tracked object's path.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct TrackTrace {
    pub object: Option<ObjectMetadata>,
    pub track_id: u64,
    pub points: Option<Vec<Point2d>>,
}

impl From<opk::TrackTraceT> for TrackTrace {
    fn from(value: opk::TrackTraceT) -> Self {
        Self {
            object: value.object.map(|nested| (*nested).into()),
            track_id: value.track_id,
            points: value
                .points
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}

/// One track-traces payload.
#[allow(missing_docs)]
#[derive(Debug)]
pub struct TrackTraces {
    pub schema_major: u16,
    pub schema_minor: u16,
    pub layer: Option<LayerInfo>,
    pub traces: Option<Vec<TrackTrace>>,
}

impl From<opk::TrackTracesT> for TrackTraces {
    fn from(value: opk::TrackTracesT) -> Self {
        Self {
            schema_major: value.schema_major,
            schema_minor: value.schema_minor,
            layer: value.layer.map(|nested| (*nested).into()),
            traces: value
                .traces
                .map(|nested| nested.into_iter().map(Into::into).collect()),
        }
    }
}
