// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::cmp::Ordering;
use std::collections::HashSet;

use pipewire::spa;
use spa::pod::{ChoiceValue, Value};
use spa::utils::{Choice, ChoiceEnum, Rectangle};

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub(crate) struct Resolution {
    pub(crate) width: u32,
    pub(crate) height: u32,
}

pub(super) fn rectangle_choice_from_value(value: Value) -> Option<ChoiceEnum<Rectangle>> {
    match value {
        Value::Rectangle(rectangle) => Some(ChoiceEnum::None(rectangle)),
        Value::Choice(ChoiceValue::Rectangle(Choice(_, choice))) => Some(choice),
        _ => None,
    }
}

pub(super) fn select_resolutions(
    choice: ChoiceEnum<Rectangle>,
    requested: Option<&Resolution>,
) -> HashSet<Resolution> {
    let requested_rectangle = requested.map(|requested| Rectangle {
        width: requested.width,
        height: requested.height,
    });
    let rectangles = rectangle_candidates(choice, requested_rectangle);

    let mut resolutions = HashSet::new();
    for rectangle in rectangles {
        let resolution = Resolution {
            width: rectangle.width,
            height: rectangle.height,
        };
        if resolution.width == 0 || resolution.height == 0 {
            continue;
        }
        if requested.is_some_and(|requested| requested != &resolution) {
            continue;
        }
        resolutions.insert(resolution);
    }
    resolutions
}

fn rectangle_candidates(
    choice: ChoiceEnum<Rectangle>,
    requested: Option<Rectangle>,
) -> Vec<Rectangle> {
    match choice {
        ChoiceEnum::None(rectangle) => vec![rectangle],
        ChoiceEnum::Enum {
            default,
            alternatives,
        } => {
            let mut rectangles = vec![default];
            rectangles.extend(alternatives);
            rectangles
        }
        ChoiceEnum::Range { default, min, max } => {
            rectangles_from_range(default, min, max, requested)
        }
        ChoiceEnum::Step {
            default,
            min,
            max,
            step,
        } => rectangles_from_step(default, min, max, step, requested),
        _ => Vec::new(),
    }
}

fn rectangles_from_range(
    default: Rectangle,
    min: Rectangle,
    max: Rectangle,
    requested: Option<Rectangle>,
) -> Vec<Rectangle> {
    let Some(requested) = requested else {
        return vec![default, min, max];
    };
    if !rectangle_is_in_range(requested, min, max) {
        return Vec::new();
    }
    vec![requested]
}

fn rectangles_from_step(
    default: Rectangle,
    min: Rectangle,
    max: Rectangle,
    step: Rectangle,
    requested: Option<Rectangle>,
) -> Vec<Rectangle> {
    if let Some(requested) = requested {
        if resolution_matches_step(requested, min, max, step) {
            return vec![requested];
        }
        return Vec::new();
    }

    let mut rectangles = vec![default];
    if let Some((aligned_min, aligned_max)) = aligned_resolution_bounds(min, max, step) {
        rectangles.extend([aligned_min, aligned_max]);
    }
    rectangles
}

fn resolution_matches_step(
    requested: Rectangle,
    min: Rectangle,
    max: Rectangle,
    step: Rectangle,
) -> bool {
    step.width > 0
        && step.height > 0
        && rectangle_is_in_range(requested, min, max)
        && requested.width.is_multiple_of(step.width)
        && requested.height.is_multiple_of(step.height)
}

fn rectangle_is_in_range(value: Rectangle, min: Rectangle, max: Rectangle) -> bool {
    compare_rectangles(value, min) != Ordering::Less
        && compare_rectangles(value, max) != Ordering::Greater
}

fn compare_rectangles(left: Rectangle, right: Rectangle) -> Ordering {
    if left == right {
        Ordering::Equal
    } else if left.width < right.width || left.height < right.height {
        Ordering::Less
    } else {
        Ordering::Greater
    }
}

fn aligned_resolution_bounds(
    min: Rectangle,
    max: Rectangle,
    step: Rectangle,
) -> Option<(Rectangle, Rectangle)> {
    let aligned_min = Rectangle {
        width: min.width.checked_next_multiple_of(step.width)?,
        height: min.height.checked_next_multiple_of(step.height)?,
    };
    let aligned_max = Rectangle {
        width: max.width - max.width.checked_rem(step.width)?,
        height: max.height - max.height.checked_rem(step.height)?,
    };

    (aligned_min.width <= aligned_max.width && aligned_min.height <= aligned_max.height)
        .then_some((aligned_min, aligned_max))
}
