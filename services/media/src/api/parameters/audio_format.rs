// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire::spa::param::audio::AudioFormat;
use pipewire::spa::param::format::{FormatProperties, MediaSubtype, MediaType};
use pipewire::spa::param::format_utils::parse_format;
use pipewire::spa::pod::deserialize::PodDeserializer;
use pipewire::spa::pod::{ChoiceValue, Object, Pod, Value, ValueArray};
use pipewire::spa::sys;
use pipewire::spa::utils::{Choice, ChoiceEnum};
use std::ffi::CStr;
use tracing::debug;

use super::spa_format_tools::{find_property_value, ids_from_spa_value, pipewire_variant_name};

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct AudioStreamFormat {
    pub(crate) sample_rate: u32,
    pub(crate) channels: u32,
    pub(crate) sample_format: String,
    pub(crate) channel_layout: Vec<String>,
    pub(crate) interleaved: bool,
}

pub(crate) fn audio_formats_from_pod(param: &Pod) -> Vec<AudioStreamFormat> {
    let Ok((media_type, media_subtype)) = parse_format(param)
        .inspect_err(|error| debug!(%error, "failed to parse SPA audio media type"))
    else {
        return Vec::new();
    };

    if media_type != MediaType::Audio || media_subtype != MediaSubtype::Raw {
        return Vec::new();
    }

    let Ok((_, Value::Object(object))) = PodDeserializer::deserialize_any_from(param.as_bytes())
        .inspect_err(|error| debug!(?error, "failed to deserialize SPA audio format"))
    else {
        return Vec::new();
    };
    audio_formats_from_object(&object)
}

fn audio_formats_from_object(object: &Object) -> Vec<AudioStreamFormat> {
    let Some(sample_rate) = find_property_value(object, FormatProperties::AudioRate.as_raw())
        .and_then(default_integer_from_value)
    else {
        debug!("missing or invalid SPA audio sample rate");
        return Vec::new();
    };
    let Some(channels) = find_property_value(object, FormatProperties::AudioChannels.as_raw())
        .and_then(default_integer_from_value)
    else {
        debug!("missing or invalid SPA audio channel count");
        return Vec::new();
    };
    let Some(sample_format_value) =
        find_property_value(object, FormatProperties::AudioFormat.as_raw())
    else {
        debug!("missing SPA audio sample format");
        return Vec::new();
    };

    let channel_layout = channel_layout_from_object(object, channels);
    spa_audio_formats_from_value(sample_format_value)
        .into_iter()
        .map(|format| AudioStreamFormat {
            sample_rate,
            channels,
            sample_format: pipewire_variant_name(format),
            channel_layout: channel_layout.clone(),
            interleaved: format.is_interleaved(),
        })
        .collect()
}

fn channel_layout_from_object(object: &Object, channels: u32) -> Vec<String> {
    let Some(Value::ValueArray(ValueArray::Id(positions))) =
        find_property_value(object, FormatProperties::AudioPosition.as_raw())
    else {
        return Vec::new();
    };
    if usize::try_from(channels) != Ok(positions.len()) {
        debug!(channels, "SPA audio position count mismatch");
        return Vec::new();
    }
    positions
        .into_iter()
        .map(|id| {
            // The longest SPA short name is "AUX4095", plus its NUL terminator.
            let mut buffer = [0; 8];
            // SAFETY: SPA writes a NUL-terminated name into the buffer or returns the fallback.
            let name = unsafe {
                CStr::from_ptr(sys::spa_type_audio_channel_make_short_name(
                    id.0,
                    buffer.as_mut_ptr(),
                    buffer.len(),
                    c"UNK".as_ptr(),
                ))
            };
            name.to_string_lossy().into_owned()
        })
        .collect()
}

fn spa_audio_formats_from_value(value: Value) -> Vec<AudioFormat> {
    let mut formats = Vec::new();
    for id in ids_from_spa_value(value) {
        let format = AudioFormat::from_raw(id.0);
        let unknown_or_encoded = format == AudioFormat::Unknown || format == AudioFormat::Encoded;
        if unknown_or_encoded || pipewire_variant_name(format) == "Unsupported" {
            debug!(format_id = id.0, "unsupported SPA sample format");
            continue;
        }
        if !formats.contains(&format) {
            formats.push(format);
        }
    }
    formats
}

fn default_integer_from_value(value: Value) -> Option<u32> {
    let number = match value {
        Value::Int(value) => value,
        Value::Choice(ChoiceValue::Int(Choice(_, choice))) => default_from_choice(choice)?,
        _ => return None,
    };
    match u32::try_from(number) {
        Ok(value @ 1..) => Some(value),
        _ => {
            debug!(number, "nonpositive SPA audio property");
            None
        }
    }
}

fn default_from_choice(choice: ChoiceEnum<i32>) -> Option<i32> {
    match choice {
        ChoiceEnum::None(default)
        | ChoiceEnum::Range { default, .. }
        | ChoiceEnum::Step { default, .. }
        | ChoiceEnum::Enum { default, .. } => Some(default),
        ChoiceEnum::Flags { .. } => None,
    }
}
