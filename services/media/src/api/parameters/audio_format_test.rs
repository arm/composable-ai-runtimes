// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::audio_format::{AudioStreamFormat, audio_formats_from_pod, default_integer_from_value};
use pipewire::spa::param::ParamType;
use pipewire::spa::param::audio::AudioFormat;
use pipewire::spa::param::format::{FormatProperties, MediaSubtype, MediaType};
use pipewire::spa::pod::serialize::PodSerializer;
use pipewire::spa::pod::{ChoiceValue, Object, Pod, Property, Value, ValueArray};
use pipewire::spa::sys;
use pipewire::spa::utils::{Choice, ChoiceEnum, ChoiceFlags, Id, SpaTypes};
use std::io::Cursor;

fn serialize_pod(value: Value) -> Vec<u8> {
    PodSerializer::serialize(Cursor::new(Vec::new()), &value)
        .unwrap()
        .0
        .into_inner()
}

fn stereo_format_object(media_type: MediaType, subtype: MediaSubtype) -> Object {
    let positions = Value::ValueArray(ValueArray::Id(vec![
        Id(sys::SPA_AUDIO_CHANNEL_FL),
        Id(sys::SPA_AUDIO_CHANNEL_FR),
    ]));
    let properties = [
        (
            FormatProperties::MediaType,
            Value::Id(Id(media_type.as_raw())),
        ),
        (
            FormatProperties::MediaSubtype,
            Value::Id(Id(subtype.as_raw())),
        ),
        (
            FormatProperties::AudioFormat,
            Value::Id(Id(AudioFormat::S16LE.as_raw())),
        ),
        (FormatProperties::AudioRate, Value::Int(48_000)),
        (FormatProperties::AudioChannels, Value::Int(2)),
        (FormatProperties::AudioPosition, positions),
    ];
    Object {
        type_: SpaTypes::ObjectParamFormat.as_raw(),
        id: ParamType::EnumFormat.as_raw(),
        properties: properties
            .into_iter()
            .map(|(key, value)| Property::new(key.as_raw(), value))
            .collect(),
    }
}

fn parse_format_object(object: Object) -> Vec<AudioStreamFormat> {
    let bytes = serialize_pod(Value::Object(object));
    audio_formats_from_pod(Pod::from_bytes(&bytes).unwrap())
}

#[test]
fn audio_formats_from_pod_decodes_raw_stereo() {
    let actual = parse_format_object(stereo_format_object(MediaType::Audio, MediaSubtype::Raw));
    let expected = [AudioStreamFormat {
        sample_rate: 48_000,
        channels: 2,
        sample_format: "S16LE".into(),
        channel_layout: vec!["FL".into(), "FR".into()],
        interleaved: true,
    }];

    assert_eq!(actual, expected);
}

#[test]
fn audio_formats_from_pod_rejects_non_format_pod() {
    let bytes = serialize_pod(Value::Int(42));
    let pod = Pod::from_bytes(&bytes).unwrap();

    assert!(audio_formats_from_pod(pod).is_empty());
}

#[test]
fn audio_formats_from_pod_rejects_raw_video() {
    assert!(
        parse_format_object(stereo_format_object(MediaType::Video, MediaSubtype::Raw)).is_empty()
    );
}

#[test]
fn audio_formats_from_pod_rejects_encoded_audio() {
    assert!(
        parse_format_object(stereo_format_object(MediaType::Audio, MediaSubtype::Mp3)).is_empty()
    );
}

fn property_value(object: &mut Object, key: FormatProperties) -> &mut Value {
    &mut object
        .properties
        .iter_mut()
        .find(|property| property.key == key.as_raw())
        .unwrap()
        .value
}

#[test]
fn audio_formats_from_pod_uses_advertised_rate_and_channel_defaults() {
    let mut object = stereo_format_object(MediaType::Audio, MediaSubtype::Raw);
    let int_choice = |choice| Value::Choice(ChoiceValue::Int(Choice(ChoiceFlags::empty(), choice)));
    *property_value(&mut object, FormatProperties::AudioRate) = int_choice(ChoiceEnum::Range {
        default: 44_100,
        min: 8_000,
        max: 192_000,
    });
    *property_value(&mut object, FormatProperties::AudioChannels) = int_choice(ChoiceEnum::Enum {
        default: 2,
        alternatives: vec![1, 4],
    });

    let actual = parse_format_object(object);
    assert_eq!(actual.len(), 1);
    assert_eq!((actual[0].sample_rate, actual[0].channels), (44_100, 2));
}

#[test]
fn audio_formats_from_pod_returns_unique_supported_sample_choices_in_order() {
    let mut object = stereo_format_object(MediaType::Audio, MediaSubtype::Raw);
    let planar = Id(AudioFormat::F32P.as_raw());
    let packed = Id(AudioFormat::S16LE.as_raw());
    *property_value(&mut object, FormatProperties::AudioFormat) =
        Value::Choice(ChoiceValue::Id(Choice(
            ChoiceFlags::empty(),
            ChoiceEnum::Enum {
                default: planar,
                alternatives: vec![
                    Id(AudioFormat::Unknown.as_raw()),
                    packed,
                    planar,
                    Id(AudioFormat::Encoded.as_raw()),
                    Id(u32::MAX),
                    packed,
                ],
            },
        )));

    let actual = parse_format_object(object);
    let samples: Vec<_> = actual
        .iter()
        .map(|format| (format.sample_format.as_str(), format.interleaved))
        .collect();
    assert_eq!(samples, [("F32P", false), ("S16LE", true)]);
}

#[test]
fn audio_formats_from_pod_rejects_invalid_required_values() {
    for (key, value) in [
        (FormatProperties::AudioRate, 0),
        (FormatProperties::AudioChannels, -1),
    ] {
        let mut object = stereo_format_object(MediaType::Audio, MediaSubtype::Raw);
        *property_value(&mut object, key) = Value::Int(value);

        assert!(
            parse_format_object(object).is_empty(),
            "accepted {key:?} = {value}"
        );
    }
}

#[test]
fn audio_formats_from_pod_preserves_format_without_a_matching_layout() {
    for positions in [None, Some(vec![Id(sys::SPA_AUDIO_CHANNEL_FL)])] {
        let mut object = stereo_format_object(MediaType::Audio, MediaSubtype::Raw);
        if let Some(positions) = positions {
            *property_value(&mut object, FormatProperties::AudioPosition) =
                Value::ValueArray(ValueArray::Id(positions));
        } else {
            object
                .properties
                .retain(|property| property.key != FormatProperties::AudioPosition.as_raw());
        }

        let actual = parse_format_object(object);
        assert_eq!(actual.len(), 1);
        assert_eq!(actual[0].channels, 2);
        assert!(actual[0].channel_layout.is_empty());
    }
}

fn integer_choice(choice: ChoiceEnum<i32>) -> Value {
    Value::Choice(ChoiceValue::Int(Choice(ChoiceFlags::empty(), choice)))
}

#[test]
fn default_integer_from_value_accepts_positive_integers() {
    for (number, expected) in [(1, 1), (48_000, 48_000), (i32::MAX, 2_147_483_647)] {
        assert_eq!(
            default_integer_from_value(Value::Int(number)),
            Some(expected)
        );
    }
}

#[test]
fn default_integer_from_value_returns_single_choice_value() {
    let value = integer_choice(ChoiceEnum::None(48_000));

    assert_eq!(default_integer_from_value(value), Some(48_000));
}

#[test]
fn default_integer_from_value_returns_range_default() {
    let value = integer_choice(ChoiceEnum::Range {
        default: 48_000,
        min: 8_000,
        max: 192_000,
    });

    assert_eq!(default_integer_from_value(value), Some(48_000));
}

#[test]
fn default_integer_from_value_returns_step_default() {
    let value = integer_choice(ChoiceEnum::Step {
        default: 48_000,
        min: 8_000,
        max: 192_000,
        step: 8_000,
    });

    assert_eq!(default_integer_from_value(value), Some(48_000));
}

#[test]
fn default_integer_from_value_returns_enum_default() {
    let value = integer_choice(ChoiceEnum::Enum {
        default: 48_000,
        alternatives: vec![8_000, 96_000],
    });

    assert_eq!(default_integer_from_value(value), Some(48_000));
}

#[test]
fn default_integer_from_value_rejects_nonpositive_values() {
    for number in [0, -1, i32::MIN] {
        for value in [Value::Int(number), integer_choice(ChoiceEnum::None(number))] {
            assert_eq!(default_integer_from_value(value), None, "accepted {number}");
        }
    }
}

#[test]
fn default_integer_from_value_rejects_unsupported_value_types() {
    for value in [
        Value::None,
        Value::Bool(true),
        Value::Long(48_000),
        Value::Float(48_000.0),
        Value::Id(Id(48_000)),
        Value::Choice(ChoiceValue::Id(Choice(
            ChoiceFlags::empty(),
            ChoiceEnum::None(Id(48_000)),
        ))),
    ] {
        assert_eq!(
            default_integer_from_value(value.clone()),
            None,
            "accepted {value:?}"
        );
    }
}

#[test]
fn default_integer_from_value_rejects_flags_choice() {
    let value = integer_choice(ChoiceEnum::Flags {
        default: 1,
        flags: vec![1, 2, 4],
    });

    assert_eq!(default_integer_from_value(value), None);
}
