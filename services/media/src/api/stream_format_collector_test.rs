// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::parameters::{
    DeviceStreamFormat, StreamFormatFilter, audio_formats_from_pod, stream_formats_from_enum_format,
};
use super::stream_format_collector::device_formats_from_pod;
use crate::device::DeviceType;
use pipewire::spa::param::ParamType;
use pipewire::spa::param::audio::AudioFormat;
use pipewire::spa::param::format::{FormatProperties, MediaSubtype, MediaType};
use pipewire::spa::param::video::VideoFormat;
use pipewire::spa::pod::serialize::PodSerializer;
use pipewire::spa::pod::{ChoiceValue, Object, Pod, Property, Value};
use pipewire::spa::utils::{Choice, ChoiceEnum, ChoiceFlags, Fraction, Id, Rectangle, SpaTypes};
use std::io::Cursor;

fn format_pod(media_type: MediaType, properties: Vec<(FormatProperties, Value)>) -> Vec<u8> {
    let headers = [
        (
            FormatProperties::MediaType,
            Value::Id(Id(media_type.as_raw())),
        ),
        (
            FormatProperties::MediaSubtype,
            Value::Id(Id(MediaSubtype::Raw.as_raw())),
        ),
    ];
    let object = Object {
        type_: SpaTypes::ObjectParamFormat.as_raw(),
        id: ParamType::EnumFormat.as_raw(),
        properties: headers
            .into_iter()
            .chain(properties)
            .map(|(key, value)| Property::new(key.as_raw(), value))
            .collect(),
    };
    PodSerializer::serialize(Cursor::new(Vec::new()), &Value::Object(object))
        .unwrap()
        .0
        .into_inner()
}

fn audio_format_pod() -> Vec<u8> {
    let samples = Value::Choice(ChoiceValue::Id(Choice(
        ChoiceFlags::empty(),
        ChoiceEnum::Enum {
            default: Id(AudioFormat::F32P.as_raw()),
            alternatives: vec![Id(AudioFormat::S16LE.as_raw())],
        },
    )));
    format_pod(
        MediaType::Audio,
        vec![
            (FormatProperties::AudioFormat, samples),
            (FormatProperties::AudioRate, Value::Int(48_000)),
            (FormatProperties::AudioChannels, Value::Int(2)),
        ],
    )
}

fn video_format_pod() -> Vec<u8> {
    let pixels = Value::Choice(ChoiceValue::Id(Choice(
        ChoiceFlags::empty(),
        ChoiceEnum::Enum {
            default: Id(VideoFormat::RGB.as_raw()),
            alternatives: vec![Id(VideoFormat::YUY2.as_raw())],
        },
    )));
    format_pod(
        MediaType::Video,
        vec![
            (FormatProperties::VideoFormat, pixels),
            (
                FormatProperties::VideoSize,
                Value::Rectangle(Rectangle {
                    width: 640,
                    height: 480,
                }),
            ),
            (
                FormatProperties::VideoFramerate,
                Value::Fraction(Fraction { num: 30, denom: 1 }),
            ),
        ],
    )
}

#[test]
fn device_formats_from_pod_wraps_camera_parser_results_as_video() {
    let bytes = video_format_pod();
    let pod = Pod::from_bytes(&bytes).unwrap();
    let expected = stream_formats_from_enum_format(pod, None);
    assert!(!expected.is_empty(), "fixture must produce video formats");

    let actual: Vec<_> = device_formats_from_pod(DeviceType::Camera, pod, None)
        .into_iter()
        .map(|format| match format {
            DeviceStreamFormat::Video(format) => format,
            DeviceStreamFormat::Audio(_) => panic!("camera result must use the video variant"),
        })
        .collect();
    assert_eq!(actual, expected);
}

#[test]
fn device_formats_from_pod_wraps_microphone_parser_results_as_audio() {
    let bytes = audio_format_pod();
    let pod = Pod::from_bytes(&bytes).unwrap();
    let expected = audio_formats_from_pod(pod);
    assert!(!expected.is_empty(), "fixture must produce audio formats");

    let actual: Vec<_> = device_formats_from_pod(DeviceType::Microphone, pod, None)
        .into_iter()
        .map(|format| match format {
            DeviceStreamFormat::Audio(format) => format,
            DeviceStreamFormat::Video(_) => panic!("microphone result must use the audio variant"),
        })
        .collect();
    assert_eq!(actual, expected);
}

#[test]
fn device_formats_from_pod_wraps_speaker_parser_results_as_audio() {
    let bytes = audio_format_pod();
    let pod = Pod::from_bytes(&bytes).unwrap();
    let expected = audio_formats_from_pod(pod);
    assert!(!expected.is_empty(), "fixture must produce audio formats");

    let actual: Vec<_> = device_formats_from_pod(DeviceType::Speaker, pod, None)
        .into_iter()
        .map(|format| match format {
            DeviceStreamFormat::Audio(format) => format,
            DeviceStreamFormat::Video(_) => panic!("speaker result must use the audio variant"),
        })
        .collect();
    assert_eq!(actual, expected);
}

#[test]
fn device_formats_from_pod_forwards_camera_filter_to_video_parser() {
    let bytes = video_format_pod();
    let pod = Pod::from_bytes(&bytes).unwrap();
    let filter = StreamFormatFilter {
        pixel_format: "YUY2".into(),
        ..Default::default()
    };
    let expected = stream_formats_from_enum_format(pod, Some(&filter));
    assert!(!expected.is_empty(), "fixture must match the filter");
    assert_ne!(
        expected,
        stream_formats_from_enum_format(pod, None),
        "filter must affect this fixture"
    );

    let actual: Vec<_> = device_formats_from_pod(DeviceType::Camera, pod, Some(&filter))
        .into_iter()
        .map(|format| match format {
            DeviceStreamFormat::Video(format) => format,
            DeviceStreamFormat::Audio(_) => panic!("camera result must use the video variant"),
        })
        .collect();
    assert_eq!(actual, expected);
}
