// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire::spa;
use spa::param::format::{FormatProperties, MediaSubtype};
use spa::param::video::VideoFormat;
use spa::pod::{ChoiceValue, Object, Value};
use spa::utils::{Choice, ChoiceEnum, Id};
use tracing::debug;

use super::stream_format::find_property_value;
pub(super) fn pixel_formats_from_object(
    object: &Object,
    media_subtype: MediaSubtype,
    requested: Option<&str>,
) -> Vec<String> {
    if media_subtype != MediaSubtype::Raw {
        let format = pipewire_variant_name(media_subtype);
        if requested.is_some_and(|requested| requested != format) {
            return Vec::new();
        }
        return vec![format];
    }

    let Some(value) = find_property_value(object, FormatProperties::VideoFormat.as_raw()) else {
        return match requested {
            Some(format) => vec![format.to_owned()],
            None => Vec::new(),
        };
    };

    let ids = ids_from_video_format_value(value);

    let mut formats = pixel_format_names_from_ids(ids);
    formats.retain(|format| requested.is_none_or(|requested| format == requested));
    formats
}

fn pixel_format_names_from_ids(ids: Vec<Id>) -> Vec<String> {
    let mut formats = Vec::new();
    for id in ids {
        let video_format = VideoFormat::from_raw(id.0);
        if video_format != VideoFormat::Unknown {
            let format = pipewire_variant_name(video_format);
            if !formats.contains(&format) {
                formats.push(format);
            }
        } else {
            debug!(format_id = id.0, "skipping unknown SPA pixel format");
        }
    }
    formats
}

fn ids_from_video_format_value(value: Value) -> Vec<Id> {
    match value {
        Value::Id(id) => vec![id],
        Value::Choice(ChoiceValue::Id(Choice(_, ChoiceEnum::None(id)))) => vec![id],
        Value::Choice(ChoiceValue::Id(Choice(
            _,
            ChoiceEnum::Enum {
                default,
                alternatives,
            },
        ))) => {
            let mut ids = Vec::with_capacity(alternatives.len() + 1);
            ids.push(default);
            ids.extend(alternatives);
            ids
        }
        _ => Vec::new(),
    }
}

fn pipewire_variant_name(value: impl std::fmt::Debug) -> String {
    let debug = format!("{value:?}");
    match debug.rsplit_once("::") {
        Some((_, name)) => name.to_string(),
        None => debug,
    }
}
