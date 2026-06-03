use super::parameters::camera_formats_from_enum_format;
use super::snapshot::SnapshotSupportedFormat;
use pipewire::spa;
use spa::param::format::{MediaSubtype, MediaType};
use spa::param::video::VideoFormat;
use spa::utils::{Choice, ChoiceEnum, ChoiceFlags, Id};
use std::io::Cursor;

fn enum_format_pod_factory(
    media_type: MediaType,
    media_subtype: MediaSubtype,
    video_format: Option<spa::pod::Value>,
) -> Vec<u8> {
    let mut properties = vec![
        spa::pod::Property::new(
            spa::param::format::FormatProperties::MediaType.as_raw(),
            spa::pod::Value::Id(Id(media_type.as_raw())),
        ),
        spa::pod::Property::new(
            spa::param::format::FormatProperties::MediaSubtype.as_raw(),
            spa::pod::Value::Id(Id(media_subtype.as_raw())),
        ),
    ];

    if let Some(format) = video_format {
        properties.push(spa::pod::Property::new(
            spa::param::format::FormatProperties::VideoFormat.as_raw(),
            format,
        ));
    }

    let object = spa::pod::Object {
        type_: spa::utils::SpaTypes::ObjectParamFormat.as_raw(),
        id: spa::param::ParamType::EnumFormat.as_raw(),
        properties,
    };

    spa::pod::serialize::PodSerializer::serialize(
        Cursor::new(Vec::new()),
        &spa::pod::Value::Object(object),
    )
    .unwrap()
    .0
    .into_inner()
}

fn id_choice_value_factory(choice: ChoiceEnum<Id>) -> spa::pod::Value {
    spa::pod::Value::Choice(spa::pod::ChoiceValue::Id(Choice(
        ChoiceFlags::empty(),
        choice,
    )))
}

fn video_format_id_factory(format: VideoFormat) -> Id {
    Id(format.as_raw())
}

#[test]
fn camera_formats_from_enum_format_ignores_non_video_formats() {
    let bytes = enum_format_pod_factory(MediaType::Audio, MediaSubtype::Raw, None);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    assert_eq!(camera_formats_from_enum_format(pod), []);
}

#[test]
fn camera_formats_from_enum_format_returns_none_choice_raw_video_format() {
    let bytes = enum_format_pod_factory(
        MediaType::Video,
        MediaSubtype::Raw,
        Some(id_choice_value_factory(ChoiceEnum::None(
            video_format_id_factory(VideoFormat::RGB),
        ))),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    assert_eq!(
        camera_formats_from_enum_format(pod),
        [SnapshotSupportedFormat::RawVideo(VideoFormat::RGB)]
    );
}

#[test]
fn camera_formats_from_enum_format_returns_unknown_raw_video_fallback() {
    let bytes = enum_format_pod_factory(
        MediaType::Video,
        MediaSubtype::Raw,
        Some(spa::pod::Value::String("Unknown".to_string())),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    assert_eq!(
        camera_formats_from_enum_format(pod),
        [SnapshotSupportedFormat::RawVideo(VideoFormat::Unknown)]
    );
}

#[test]
fn camera_formats_from_enum_format_returns_single_raw_video_format() {
    let bytes = enum_format_pod_factory(
        MediaType::Video,
        MediaSubtype::Raw,
        Some(spa::pod::Value::Id(video_format_id_factory(
            VideoFormat::RGB,
        ))),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    assert_eq!(
        camera_formats_from_enum_format(pod),
        [SnapshotSupportedFormat::RawVideo(VideoFormat::RGB)]
    );
}

#[test]
fn camera_formats_from_enum_format_expands_raw_video_format_enum_choices() {
    let format = id_choice_value_factory(ChoiceEnum::Enum {
        default: video_format_id_factory(VideoFormat::RGB),
        alternatives: vec![
            video_format_id_factory(VideoFormat::RGB),
            video_format_id_factory(VideoFormat::YUY2),
            video_format_id_factory(VideoFormat::I420),
        ],
    });
    let bytes = enum_format_pod_factory(MediaType::Video, MediaSubtype::Raw, Some(format));
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    assert_eq!(
        camera_formats_from_enum_format(pod),
        [
            SnapshotSupportedFormat::RawVideo(VideoFormat::RGB),
            SnapshotSupportedFormat::RawVideo(VideoFormat::YUY2),
            SnapshotSupportedFormat::RawVideo(VideoFormat::I420),
        ]
    );
}

#[test]
fn camera_formats_from_enum_format_preserves_encoded_video_subtype() {
    let bytes = enum_format_pod_factory(MediaType::Video, MediaSubtype::Mjpg, None);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    assert_eq!(
        camera_formats_from_enum_format(pod),
        [SnapshotSupportedFormat::EncodedVideo(MediaSubtype::Mjpg)]
    );
}
