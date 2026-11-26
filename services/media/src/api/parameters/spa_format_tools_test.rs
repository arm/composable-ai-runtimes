// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::spa_format_tools::{find_property_value, ids_from_spa_value, pipewire_variant_name};
use pipewire::spa::param::ParamType;
use pipewire::spa::param::format::FormatProperties;
use pipewire::spa::param::video::VideoFormat;
use pipewire::spa::pod::{ChoiceValue, Object, Property, Value, ValueArray};
use pipewire::spa::utils::{Choice, ChoiceEnum, ChoiceFlags, Id, SpaTypes};

fn format_object(properties: Vec<Property>) -> Object {
    Object {
        type_: SpaTypes::ObjectParamFormat.as_raw(),
        id: ParamType::EnumFormat.as_raw(),
        properties,
    }
}

#[test]
fn find_property_value_returns_the_value_for_the_requested_key() {
    let object = format_object(vec![
        Property::new(FormatProperties::AudioRate.as_raw(), Value::Int(44_100)),
        Property::new(FormatProperties::AudioChannels.as_raw(), Value::Int(6)),
    ]);

    let actual = find_property_value(&object, FormatProperties::AudioChannels.as_raw());

    assert_eq!(actual, Some(Value::Int(6)));
}

#[test]
fn find_property_value_returns_none_when_the_key_is_absent() {
    let object = format_object(vec![Property::new(
        FormatProperties::AudioRate.as_raw(),
        Value::Int(48_000),
    )]);

    let actual = find_property_value(&object, FormatProperties::AudioFormat.as_raw());

    assert_eq!(actual, None);
}

#[test]
fn ids_from_spa_value_returns_a_plain_id() {
    let value = Value::Id(Id(42));

    let actual = ids_from_spa_value(value);

    assert_eq!(actual, [Id(42)]);
}

#[test]
fn ids_from_spa_value_returns_a_single_choice_id() {
    let value = Value::Choice(ChoiceValue::Id(Choice(
        ChoiceFlags::empty(),
        ChoiceEnum::None(Id(42)),
    )));

    let actual = ids_from_spa_value(value);

    assert_eq!(actual, [Id(42)]);
}

#[test]
fn ids_from_spa_value_preserves_enum_order_and_duplicates() {
    let value = Value::Choice(ChoiceValue::Id(Choice(
        ChoiceFlags::empty(),
        ChoiceEnum::Enum {
            default: Id(2),
            alternatives: vec![Id(3), Id(2), Id(1), Id(3)],
        },
    )));

    let actual = ids_from_spa_value(value);

    assert_eq!(actual, [Id(2), Id(3), Id(2), Id(1), Id(3)]);
}

#[test]
fn ids_from_spa_value_returns_empty_for_unsupported_value_types() {
    for value in [
        Value::None,
        Value::Int(42),
        Value::ValueArray(ValueArray::Id(vec![Id(42)])),
        Value::Choice(ChoiceValue::Int(Choice(
            ChoiceFlags::empty(),
            ChoiceEnum::None(42),
        ))),
    ] {
        let actual = ids_from_spa_value(value.clone());

        assert!(actual.is_empty(), "accepted {value:?}");
    }
}

#[test]
fn ids_from_spa_value_returns_empty_for_unsupported_id_choices() {
    for choice in [
        ChoiceEnum::Range {
            default: Id(2),
            min: Id(1),
            max: Id(3),
        },
        ChoiceEnum::Step {
            default: Id(2),
            min: Id(1),
            max: Id(3),
            step: Id(1),
        },
        ChoiceEnum::Flags {
            default: Id(1),
            flags: vec![Id(1), Id(2)],
        },
    ] {
        let value = Value::Choice(ChoiceValue::Id(Choice(ChoiceFlags::empty(), choice)));

        let actual = ids_from_spa_value(value.clone());

        assert!(actual.is_empty(), "accepted {value:?}");
    }
}

#[test]
fn pipewire_variant_name_removes_the_type_prefix() {
    let format = VideoFormat::RGB;

    let actual = pipewire_variant_name(format);

    assert_eq!(actual, "RGB");
}

#[test]
fn pipewire_variant_name_preserves_unqualified_debug_text() {
    let value = 42;

    let actual = pipewire_variant_name(value);

    assert_eq!(actual, "42");
}
