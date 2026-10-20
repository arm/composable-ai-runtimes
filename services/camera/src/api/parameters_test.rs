// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::api::parameters::{FrameRate, Resolution, StreamFormat, StreamFormatFilter};

use super::parameters::stream_formats_from_enum_format as parse_stream_formats;
use pipewire::spa;
use spa::param::format::{MediaSubtype, MediaType};
use spa::param::video::VideoFormat;
use spa::pod::{ChoiceValue, Value};
use spa::utils::{Choice, ChoiceEnum, ChoiceFlags, Fraction, Id, Rectangle};
use std::io::Cursor;

fn stream_formats_from_enum_format(param: &spa::pod::Pod) -> Vec<StreamFormat> {
    parse_stream_formats(param, None)
}

fn pixel_format(format: VideoFormat) -> Id {
    Id(format.as_raw())
}

fn resolution(width: u32, height: u32) -> Rectangle {
    Rectangle { width, height }
}

fn frame_rate(numerator: u32, denominator: u32) -> Fraction {
    Fraction {
        num: numerator,
        denom: denominator,
    }
}

fn enum_format_pod(
    pixel_formats: ChoiceEnum<Id>,
    resolutions: ChoiceEnum<Rectangle>,
    frame_rates: ChoiceEnum<Fraction>,
) -> Vec<u8> {
    enum_format_pod_for_media_type(MediaType::Video, pixel_formats, resolutions, frame_rates)
}

fn enum_format_pod_for_media_type(
    media_type: MediaType,
    pixel_formats: ChoiceEnum<Id>,
    resolutions: ChoiceEnum<Rectangle>,
    frame_rates: ChoiceEnum<Fraction>,
) -> Vec<u8> {
    let pixel_formats = Value::Choice(ChoiceValue::Id(Choice(ChoiceFlags::empty(), pixel_formats)));
    let resolutions = Value::Choice(ChoiceValue::Rectangle(Choice(
        ChoiceFlags::empty(),
        resolutions,
    )));
    let frame_rates = Value::Choice(ChoiceValue::Fraction(Choice(
        ChoiceFlags::empty(),
        frame_rates,
    )));

    let object = spa::pod::Object {
        type_: spa::utils::SpaTypes::ObjectParamFormat.as_raw(),
        id: spa::param::ParamType::EnumFormat.as_raw(),
        properties: vec![
            spa::pod::Property::new(
                spa::param::format::FormatProperties::MediaType.as_raw(),
                Value::Id(Id(media_type.as_raw())),
            ),
            spa::pod::Property::new(
                spa::param::format::FormatProperties::MediaSubtype.as_raw(),
                Value::Id(Id(MediaSubtype::Raw.as_raw())),
            ),
            spa::pod::Property::new(
                spa::param::format::FormatProperties::VideoFormat.as_raw(),
                pixel_formats,
            ),
            spa::pod::Property::new(
                spa::param::format::FormatProperties::VideoSize.as_raw(),
                resolutions,
            ),
            spa::pod::Property::new(
                spa::param::format::FormatProperties::VideoFramerate.as_raw(),
                frame_rates,
            ),
        ],
    };

    spa::pod::serialize::PodSerializer::serialize(
        Cursor::new(Vec::new()),
        &spa::pod::Value::Object(object),
    )
    .unwrap()
    .0
    .into_inner()
}

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

#[test]
fn stream_formats_from_enum_format_returns_fixed_stream_format() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::None(resolution(1920, 1080)),
        ChoiceEnum::None(frame_rate(30, 1)),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod);

    let expected = vec![StreamFormat {
        resolution: Resolution {
            width: 1920,
            height: 1080,
        },
        pixel_format: "RGB".to_string(),
        frame_rate: FrameRate {
            numerator: 30,
            denominator: 1,
        },
    }];

    assert_eq!(actual, expected);
}

#[test]
fn stream_formats_from_enum_format_expands_pixel_format_enum_choices() {
    let pixel_formats = ChoiceEnum::Enum {
        default: pixel_format(VideoFormat::RGB),
        alternatives: vec![pixel_format(VideoFormat::YUY2)],
    };
    let resolutions = ChoiceEnum::None(resolution(1920, 1080));
    let frame_rates = ChoiceEnum::None(frame_rate(30, 1));

    let bytes = enum_format_pod(pixel_formats, resolutions, frame_rates);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod);

    let expected = vec![
        StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        },
        StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "YUY2".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        },
    ];

    assert_eq!(actual, expected);
}

#[test]
fn stream_formats_from_enum_format_ignores_unknown_pixel_formats() {
    let pixel_formats = ChoiceEnum::Enum {
        default: pixel_format(VideoFormat::Unknown),
        alternatives: vec![pixel_format(VideoFormat::RGB)],
    };
    let resolutions = ChoiceEnum::None(resolution(1920, 1080));
    let frame_rates = ChoiceEnum::None(frame_rate(30, 1));

    let bytes = enum_format_pod(pixel_formats, resolutions, frame_rates);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod);

    let expected = vec![StreamFormat {
        resolution: Resolution {
            width: 1920,
            height: 1080,
        },
        pixel_format: "RGB".to_string(),
        frame_rate: FrameRate {
            numerator: 30,
            denominator: 1,
        },
    }];

    assert_eq!(actual, expected);
}

#[test]
fn stream_formats_from_enum_format_expands_resolution_enum_choices() {
    let pixel_formats = ChoiceEnum::None(pixel_format(VideoFormat::RGB));
    let resolutions = ChoiceEnum::Enum {
        default: resolution(1920, 1080),
        alternatives: vec![resolution(400, 400)],
    };
    let frame_rates = ChoiceEnum::None(frame_rate(30, 1));

    let bytes = enum_format_pod(pixel_formats, resolutions, frame_rates);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod);

    let expected = vec![
        StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        },
        StreamFormat {
            resolution: Resolution {
                width: 400,
                height: 400,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        },
    ];

    assert_eq!(actual.len(), expected.len());
    assert!(expected.iter().all(|format| actual.contains(format)));
}

#[test]
fn stream_formats_from_enum_format_expands_frame_rate_enum_choices() {
    let pixel_formats = ChoiceEnum::None(pixel_format(VideoFormat::RGB));
    let resolutions = ChoiceEnum::None(resolution(1920, 1080));
    let frame_rates = ChoiceEnum::Enum {
        default: frame_rate(30, 1),
        alternatives: vec![frame_rate(60, 1)],
    };

    let bytes = enum_format_pod(pixel_formats, resolutions, frame_rates);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod);

    let expected = [
        StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        },
        StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 60,
                denominator: 1,
            },
        },
    ];

    assert_eq!(actual.len(), expected.len());
    assert!(expected.iter().all(|format| actual.contains(format)));
}

#[test]
fn stream_formats_from_enum_format_skips_zero_frame_rates_without_losing_valid_rates() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::None(resolution(640, 480)),
        ChoiceEnum::Enum {
            default: frame_rate(0, 1),
            alternatives: vec![
                frame_rate(30, 0),
                frame_rate(0, 0),
                frame_rate(30, 1),
                frame_rate(60, 2),
            ],
        },
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();
    let rates = stream_formats_from_enum_format(pod)
        .into_iter()
        .map(|format| format.frame_rate)
        .collect::<Vec<_>>();

    assert_eq!(
        rates,
        vec![FrameRate {
            numerator: 30,
            denominator: 1
        }]
    );
}

#[test]
fn frame_rate_equality_compares_values_and_handles_invalid_denominators() {
    for ((left_num, left_denom), (right_num, right_denom), equal) in [
        ((30, 1), (60, 2), true),
        ((30000, 1001), (30, 1), false),
        ((0, 0), (30, 1), false),
        ((0, 0), (0, 0), true),
    ] {
        let left = FrameRate {
            numerator: left_num,
            denominator: left_denom,
        };
        let right = FrameRate {
            numerator: right_num,
            denominator: right_denom,
        };
        assert_eq!(left == right, equal, "{left:?} compared with {right:?}");
        assert_eq!(
            std::collections::HashSet::from([left.clone()]).contains(&right),
            equal,
            "hashing {left:?} and {right:?} must agree with equality",
        );
    }
}

#[test]
fn frame_rate_ordering_compares_values_and_handles_invalid_denominators() {
    use std::cmp::Ordering::{Equal, Greater, Less};

    for ((left_num, left_denom), (right_num, right_denom), expected) in [
        ((30, 1), (60, 2), Some(Equal)),
        ((30000, 1001), (30, 1), Some(Less)),
        ((u32::MAX, 1), (1, u32::MAX), Some(Greater)),
        ((0, 0), (30, 1), None),
        ((0, 0), (0, 0), Some(Equal)),
    ] {
        let left = FrameRate::from(frame_rate(left_num, left_denom));
        let right = FrameRate::from(frame_rate(right_num, right_denom));
        assert_eq!(
            left.partial_cmp(&right),
            expected,
            "{left:?} compared with {right:?}"
        );
    }
}

#[test]
fn stream_formats_from_enum_format_matches_and_deduplicates_equivalent_frame_rates() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::None(resolution(1920, 1080)),
        ChoiceEnum::Enum {
            default: frame_rate(60, 2),
            alternatives: vec![frame_rate(30, 1)],
        },
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();
    let filter = StreamFormatFilter {
        resolution: None,
        pixel_format: String::new(),
        frame_rate: Some(FrameRate {
            numerator: 60,
            denominator: 2,
        }),
    };

    let actual = parse_stream_formats(pod, Some(&filter));
    assert_eq!(actual[0].frame_rate.numerator, 30);
    assert_eq!(actual[0].frame_rate.denominator, 1);

    assert_eq!(
        actual,
        [StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        }]
    );
}

#[test]
fn stream_formats_from_enum_format_deduplicates_repeated_choices() {
    let pixel_formats = ChoiceEnum::Enum {
        default: pixel_format(VideoFormat::RGB),
        alternatives: vec![
            pixel_format(VideoFormat::RGB),
            pixel_format(VideoFormat::YUY2),
        ],
    };
    let resolutions = ChoiceEnum::Enum {
        default: resolution(1920, 1080),
        alternatives: vec![resolution(1920, 1080), resolution(1920, 1080)],
    };
    let frame_rates = ChoiceEnum::None(frame_rate(30, 1));

    let bytes = enum_format_pod(pixel_formats, resolutions, frame_rates);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod);

    let expected = vec![
        StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        },
        StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "YUY2".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        },
    ];

    assert_eq!(actual, expected);
}

#[test]
fn stream_formats_from_enum_format_ignores_non_video_formats() {
    let bytes = enum_format_pod_for_media_type(
        MediaType::Audio,
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::None(resolution(1920, 1080)),
        ChoiceEnum::None(frame_rate(30, 1)),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod);

    assert!(actual.is_empty());
}

#[test]
fn stream_formats_from_enum_format_returns_empty_for_malformed_pod() {
    let bytes = spa::pod::serialize::PodSerializer::serialize(
        Cursor::new(Vec::new()),
        &Value::String("not an EnumFormat object".to_string()),
    )
    .unwrap()
    .0
    .into_inner();
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod);

    assert!(actual.is_empty());
}

#[test]
fn stream_formats_from_enum_format_uses_requested_values_for_missing_properties() {
    let bytes = enum_format_pod_factory(MediaType::Video, MediaSubtype::Raw, None);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();
    let filter = StreamFormatFilter {
        resolution: Some(Resolution {
            width: 1920,
            height: 1080,
        }),
        pixel_format: "RGB".to_string(),
        frame_rate: Some(FrameRate {
            numerator: 60,
            denominator: 2,
        }),
    };

    let actual = parse_stream_formats(pod, Some(&filter));
    assert_eq!(actual[0].frame_rate.numerator, 30);
    assert_eq!(actual[0].frame_rate.denominator, 1);

    assert_eq!(
        actual,
        [StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        }]
    );
}

#[test]
fn stream_formats_from_enum_format_returns_default_and_aligned_bounds_for_frame_rate_steps() {
    let pixel_formats = ChoiceEnum::None(pixel_format(VideoFormat::RGB));
    let resolutions = ChoiceEnum::None(resolution(1920, 1080));
    let frame_rates = ChoiceEnum::Step {
        default: frame_rate(16, 1),
        min: frame_rate(10, 1),
        max: frame_rate(30, 1),
        step: frame_rate(8, 1),
    };

    let bytes = enum_format_pod(pixel_formats, resolutions, frame_rates);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod)
        .into_iter()
        .map(|format| format.frame_rate)
        .collect::<Vec<_>>();
    let expected = [
        FrameRate {
            numerator: 16,
            denominator: 1,
        },
        FrameRate {
            numerator: 24,
            denominator: 1,
        },
    ];

    assert_eq!(actual.len(), expected.len());
    assert!(expected.iter().all(|rate| actual.contains(rate)));
}

#[test]
fn stream_formats_from_enum_format_returns_default_and_aligned_bounds_for_resolution_steps() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::Step {
            default: resolution(16, 16),
            min: resolution(10, 10),
            max: resolution(30, 30),
            step: resolution(8, 8),
        },
        ChoiceEnum::None(frame_rate(30, 1)),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod)
        .into_iter()
        .map(|format| format.resolution)
        .collect::<Vec<_>>();
    let expected = vec![
        Resolution {
            width: 16,
            height: 16,
        },
        Resolution {
            width: 24,
            height: 24,
        },
    ];

    assert_eq!(actual.len(), expected.len());
    assert!(
        expected
            .iter()
            .all(|resolution| actual.contains(resolution))
    );
}

#[test]
fn stream_formats_from_enum_format_filters_step_choices_without_expanding_them() {
    let bytes = enum_format_pod(
        ChoiceEnum::Enum {
            default: pixel_format(VideoFormat::RGB),
            alternatives: vec![pixel_format(VideoFormat::YUY2)],
        },
        ChoiceEnum::Step {
            default: resolution(640, 480),
            min: resolution(320, 240),
            max: resolution(1920, 1080),
            step: resolution(16, 16),
        },
        ChoiceEnum::Step {
            default: frame_rate(30, 1),
            min: frame_rate(15, 1),
            max: frame_rate(60, 1),
            step: frame_rate(15, 1),
        },
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();
    let filter = StreamFormatFilter {
        resolution: Some(Resolution {
            width: 1280,
            height: 720,
        }),
        pixel_format: "YUY2".to_string(),
        frame_rate: Some(FrameRate {
            numerator: 45,
            denominator: 1,
        }),
    };

    let actual = parse_stream_formats(pod, Some(&filter));
    let expected = vec![StreamFormat {
        resolution: Resolution {
            width: 1280,
            height: 720,
        },
        pixel_format: "YUY2".to_string(),
        frame_rate: FrameRate {
            numerator: 45,
            denominator: 1,
        },
    }];

    assert_eq!(actual, expected);
}

#[test]
fn stream_formats_from_enum_format_uses_directly_divisible_frame_rate_steps() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::None(resolution(1920, 1080)),
        ChoiceEnum::Step {
            default: frame_rate(16, 1),
            min: frame_rate(10, 1),
            max: frame_rate(30, 1),
            step: frame_rate(8, 1),
        },
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();
    let valid_filter = StreamFormatFilter {
        resolution: None,
        pixel_format: String::new(),
        frame_rate: Some(FrameRate {
            numerator: 16,
            denominator: 1,
        }),
    };
    let invalid_filter = StreamFormatFilter {
        resolution: None,
        pixel_format: String::new(),
        frame_rate: Some(FrameRate {
            numerator: 18,
            denominator: 1,
        }),
    };

    let valid = parse_stream_formats(pod, Some(&valid_filter));
    let invalid = parse_stream_formats(pod, Some(&invalid_filter));

    assert_eq!(
        valid,
        [StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 16,
                denominator: 1,
            },
        }]
    );
    assert!(invalid.is_empty());
}

#[test]
fn stream_formats_from_enum_format_filters_non_default_range_values() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::Range {
            default: resolution(640, 480),
            min: resolution(320, 240),
            max: resolution(1920, 1080),
        },
        ChoiceEnum::Range {
            default: frame_rate(30, 1),
            min: frame_rate(15, 1),
            max: frame_rate(60, 1),
        },
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();
    let filter = StreamFormatFilter {
        resolution: Some(Resolution {
            width: 1280,
            height: 720,
        }),
        pixel_format: String::new(),
        frame_rate: Some(FrameRate {
            numerator: 45,
            denominator: 1,
        }),
    };

    let actual = parse_stream_formats(pod, Some(&filter));

    assert_eq!(
        actual,
        vec![StreamFormat {
            resolution: Resolution {
                width: 1280,
                height: 720,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 45,
                denominator: 1,
            },
        }]
    );
}

#[test]
fn stream_formats_from_enum_format_matches_pipewire_rectangle_ranges() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::Range {
            default: resolution(1280, 720),
            min: resolution(640, 480),
            max: resolution(1920, 1080),
        },
        ChoiceEnum::None(frame_rate(30, 1)),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();
    let filter = StreamFormatFilter {
        resolution: Some(Resolution {
            width: 2560,
            height: 720,
        }),
        pixel_format: String::new(),
        frame_rate: None,
    };

    let actual = parse_stream_formats(pod, Some(&filter));

    assert_eq!(
        actual,
        [StreamFormat {
            resolution: Resolution {
                width: 2560,
                height: 720,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        }]
    );
}

#[test]
fn stream_formats_from_enum_format_rejects_offset_aligned_resolution_steps() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::Step {
            default: resolution(16, 16),
            min: resolution(10, 10),
            max: resolution(30, 30),
            step: resolution(8, 8),
        },
        ChoiceEnum::None(frame_rate(30, 1)),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();
    let filter = StreamFormatFilter {
        resolution: Some(Resolution {
            width: 18,
            height: 18,
        }),
        pixel_format: String::new(),
        frame_rate: None,
    };

    let actual = parse_stream_formats(pod, Some(&filter));

    assert!(actual.is_empty());
}

#[test]
fn stream_formats_from_enum_format_returns_default_and_bounds_for_frame_rate_ranges() {
    let pixel_formats = ChoiceEnum::None(pixel_format(VideoFormat::RGB));
    let resolutions = ChoiceEnum::None(resolution(1920, 1080));
    let frame_rates = ChoiceEnum::Range {
        default: frame_rate(30, 1),
        min: frame_rate(15, 1),
        max: frame_rate(60, 1),
    };

    let bytes = enum_format_pod(pixel_formats, resolutions, frame_rates);
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod)
        .into_iter()
        .map(|format| format.frame_rate)
        .collect::<Vec<_>>();
    let expected = [
        FrameRate {
            numerator: 30,
            denominator: 1,
        },
        FrameRate {
            numerator: 15,
            denominator: 1,
        },
        FrameRate {
            numerator: 60,
            denominator: 1,
        },
    ];

    assert_eq!(actual.len(), expected.len());
    assert!(expected.iter().all(|rate| actual.contains(rate)));
}

#[test]
fn stream_formats_from_enum_format_returns_default_and_bounds_for_resolution_ranges() {
    let bytes = enum_format_pod(
        ChoiceEnum::None(pixel_format(VideoFormat::RGB)),
        ChoiceEnum::Range {
            default: resolution(1280, 720),
            min: resolution(640, 480),
            max: resolution(1920, 1080),
        },
        ChoiceEnum::None(frame_rate(30, 1)),
    );
    let pod = spa::pod::Pod::from_bytes(&bytes).unwrap();

    let actual = stream_formats_from_enum_format(pod)
        .into_iter()
        .map(|format| format.resolution)
        .collect::<Vec<_>>();
    let expected = vec![
        Resolution {
            width: 1280,
            height: 720,
        },
        Resolution {
            width: 640,
            height: 480,
        },
        Resolution {
            width: 1920,
            height: 1080,
        },
    ];

    assert_eq!(actual.len(), expected.len());
    assert!(
        expected
            .iter()
            .all(|resolution| actual.contains(resolution))
    );
}
