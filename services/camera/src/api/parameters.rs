use pipewire::spa;
use spa::param::video::VideoFormat;
use spa::pod::{ChoiceValue, Value};
use spa::utils::{Choice, ChoiceEnum, Id};

use super::snapshot::SnapshotSupportedFormat;

pub(crate) fn camera_formats_from_enum_format(
    param: &spa::pod::Pod,
) -> Vec<SnapshotSupportedFormat> {
    let Ok((media_type, media_subtype)) = spa::param::format_utils::parse_format(param) else {
        return Vec::new();
    };

    if media_type != spa::param::format::MediaType::Video {
        return Vec::new();
    }

    if media_subtype != spa::param::format::MediaSubtype::Raw {
        return vec![SnapshotSupportedFormat::EncodedVideo(media_subtype)];
    }

    raw_video_format_ids(param)
        .map(dedupe_formats_from_ids)
        .unwrap_or_else(|| fallback_to_raw(param).into_iter().collect())
}

fn raw_video_format_ids(param: &spa::pod::Pod) -> Option<Vec<Id>> {
    let (_, value) =
        spa::pod::deserialize::PodDeserializer::deserialize_any_from(param.as_bytes()).ok()?;
    let Value::Object(object) = value else {
        return None;
    };

    let property = object.properties.into_iter().find(|property| {
        property.key == spa::param::format::FormatProperties::VideoFormat.as_raw()
    })?;

    ids_from_video_format_value(property.value)
}

fn ids_from_video_format_value(value: Value) -> Option<Vec<Id>> {
    match value {
        Value::Id(id) => Some(vec![id]),
        Value::Choice(ChoiceValue::Id(Choice(_, ChoiceEnum::None(id)))) => Some(vec![id]),
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
            Some(ids)
        }
        _ => None,
    }
}

fn dedupe_formats_from_ids(ids: Vec<Id>) -> Vec<SnapshotSupportedFormat> {
    let mut formats: Vec<SnapshotSupportedFormat> = Vec::new();

    for id in ids {
        let format = SnapshotSupportedFormat::RawVideo(VideoFormat::from_raw(id.0));
        if !formats
            .iter()
            .any(|existing| existing.has_same_name(&format))
        {
            formats.push(format);
        }
    }

    formats
}

fn fallback_to_raw(param: &spa::pod::Pod) -> Option<SnapshotSupportedFormat> {
    let mut video_info = spa::param::video::VideoInfoRaw::new();
    video_info.parse(param).ok()?;
    Some(SnapshotSupportedFormat::RawVideo(video_info.format()))
}
