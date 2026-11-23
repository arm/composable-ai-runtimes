// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire::spa::pod::{ChoiceValue, Object, Value};
use pipewire::spa::utils::{Choice, ChoiceEnum, Id};

pub(super) fn find_property_value(object: &Object, key: u32) -> Option<Value> {
    object
        .properties
        .iter()
        .find(|property| property.key == key)
        .map(|property| property.value.clone())
}

pub(super) fn ids_from_spa_value(value: Value) -> Vec<Id> {
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

pub(super) fn pipewire_variant_name(value: impl std::fmt::Debug) -> String {
    let debug = format!("{value:?}");
    match debug.rsplit_once("::") {
        Some((_, name)) => name.to_string(),
        None => debug,
    }
}
