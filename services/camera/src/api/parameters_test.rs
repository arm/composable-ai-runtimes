use super::parameters::camera_formats_from_enum_format;
use super::snapshot::SnapshotSupportedFormat;
use pipewire::spa;
use spa::param::format::MediaSubtype;
use spa::param::video::VideoFormat;
use std::io::Cursor;

fn enum_format_pod(properties: Vec<spa::pod::Property>) -> Vec<u8> {
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

fn video_raw_properties(format: spa::pod::Value) -> Vec<spa::pod::Property> {
    vec![
        spa::pod::Property::new(
            spa::param::format::FormatProperties::MediaType.as_raw(),
            spa::pod::Value::Id(spa::utils::Id(
                spa::param::format::MediaType::Video.as_raw(),
            )),
        ),
        spa::pod::Property::new(
            spa::param::format::FormatProperties::MediaSubtype.as_raw(),
            spa::pod::Value::Id(spa::utils::Id(
                spa::param::format::MediaSubtype::Raw.as_raw(),
            )),
        ),
        spa::pod::Property::new(
            spa::param::format::FormatProperties::VideoFormat.as_raw(),
            format,
        ),
    ]
}

#[test]
fn camera_formats_from_enum_format_returns_single_raw_video_format() {
    let bytes = enum_format_pod(video_raw_properties(spa::pod::Value::Id(spa::utils::Id(
        VideoFormat::RGB.as_raw(),
    ))));
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    assert_eq!(
        camera_formats_from_enum_format(pod),
        [SnapshotSupportedFormat::RawVideo(VideoFormat::RGB)]
    );
}

#[test]
fn camera_formats_from_enum_format_expands_raw_video_format_enum_choices() {
    let format = spa::pod::Value::Choice(spa::pod::ChoiceValue::Id(spa::utils::Choice(
        spa::utils::ChoiceFlags::empty(),
        spa::utils::ChoiceEnum::Enum {
            default: spa::utils::Id(VideoFormat::RGB.as_raw()),
            alternatives: vec![
                spa::utils::Id(VideoFormat::RGB.as_raw()),
                spa::utils::Id(VideoFormat::YUY2.as_raw()),
                spa::utils::Id(VideoFormat::I420.as_raw()),
            ],
        },
    )));
    let bytes = enum_format_pod(video_raw_properties(format));
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
    let bytes = enum_format_pod(vec![
        spa::pod::Property::new(
            spa::param::format::FormatProperties::MediaType.as_raw(),
            spa::pod::Value::Id(spa::utils::Id(
                spa::param::format::MediaType::Video.as_raw(),
            )),
        ),
        spa::pod::Property::new(
            spa::param::format::FormatProperties::MediaSubtype.as_raw(),
            spa::pod::Value::Id(spa::utils::Id(MediaSubtype::Mjpg.as_raw())),
        ),
    ]);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    assert_eq!(
        camera_formats_from_enum_format(pod),
        [SnapshotSupportedFormat::EncodedVideo(MediaSubtype::Mjpg)]
    );
}
