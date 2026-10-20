// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire::spa;
use spa::pod::Value;
use std::collections::HashSet;
use tracing::debug;

use super::frame_rate::{fraction_choice_from_value, select_frame_rates};
use super::pixel_format::pixel_formats_from_object;
use super::resolution::{rectangle_choice_from_value, select_resolutions};
use super::{FrameRate, Resolution};

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct StreamFormat {
    pub(crate) resolution: Resolution,
    pub(crate) pixel_format: String,
    pub(crate) frame_rate: FrameRate,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub(crate) struct StreamFormatFilter {
    pub(crate) resolution: Option<Resolution>,
    pub(crate) pixel_format: String,
    pub(crate) frame_rate: Option<FrameRate>,
}

pub(crate) fn stream_formats_from_enum_format(
    param: &spa::pod::Pod,
    filter: Option<&StreamFormatFilter>,
) -> Vec<StreamFormat> {
    let Ok((media_type, media_subtype)) = spa::param::format_utils::parse_format(param)
        .inspect_err(|error| debug!(%error, "failed to parse SPA stream media type"))
    else {
        return Vec::new();
    };

    if media_type != spa::param::format::MediaType::Video {
        debug!(?media_type, "skipping non-video SPA stream format");
        return Vec::new();
    }

    let Ok((_, Value::Object(object))) =
        spa::pod::deserialize::PodDeserializer::deserialize_any_from(param.as_bytes())
            .inspect_err(|error| debug!(?error, "failed to deserialize SPA stream format"))
    else {
        return Vec::new();
    };

    let requested_pixel_format = filter
        .map(|filter| filter.pixel_format.as_str())
        .filter(|format| !format.is_empty());
    let requested_resolution = filter.and_then(|filter| filter.resolution.as_ref());
    let requested_frame_rate = filter.and_then(|filter| filter.frame_rate.as_ref());

    let pixel_formats = pixel_formats_from_object(&object, media_subtype, requested_pixel_format);

    let resolutions = find_property_value(
        &object,
        spa::param::format::FormatProperties::VideoSize.as_raw(),
    )
    .map(|value| match rectangle_choice_from_value(value) {
        Some(choice) => select_resolutions(choice, requested_resolution),
        None => HashSet::new(),
    })
    .unwrap_or_else(|| requested_resolution.cloned().into_iter().collect());

    let frame_rates = find_property_value(
        &object,
        spa::param::format::FormatProperties::VideoFramerate.as_raw(),
    )
    .map(|value| match fraction_choice_from_value(value) {
        Some(choice) => select_frame_rates(choice, requested_frame_rate),
        None => HashSet::new(),
    })
    .unwrap_or_else(|| {
        requested_frame_rate
            .map(FrameRate::reduced)
            .into_iter()
            .collect()
    });

    let mut stream_formats =
        Vec::with_capacity(pixel_formats.len() * resolutions.len() * frame_rates.len());
    for pixel_format in pixel_formats {
        for resolution in &resolutions {
            for frame_rate in &frame_rates {
                stream_formats.push(StreamFormat {
                    resolution: resolution.clone(),
                    pixel_format: pixel_format.clone(),
                    frame_rate: frame_rate.clone(),
                });
            }
        }
    }

    stream_formats
}

pub(super) fn find_property_value(object: &spa::pod::Object, key: u32) -> Option<Value> {
    object
        .properties
        .iter()
        .find(|property| property.key == key)
        .map(|property| property.value.clone())
}
