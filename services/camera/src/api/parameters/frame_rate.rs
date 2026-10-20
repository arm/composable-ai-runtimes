// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire::spa;
use spa::pod::{ChoiceValue, Value};
use spa::utils::{Choice, ChoiceEnum, Fraction};
use std::cmp::Ordering;
use std::collections::HashSet;
use std::hash::{Hash, Hasher};
use tracing::debug;

/// A rational frame rate with equality and hashing based on its numerical value.
/// Equivalent rates such as 30/1 and 60/2 compare equal and hash identically,
/// without modifying the stored numerator or denominator. Zero-denominator
/// values use field-based equality and hashing.
#[derive(Clone, Debug, Eq)]
pub(crate) struct FrameRate {
    pub(crate) numerator: u32,
    pub(crate) denominator: u32,
}

impl FrameRate {
    pub(super) fn reduced(&self) -> Self {
        if self.denominator == 0 {
            return self.clone();
        }

        let divisor =
            greatest_common_divisor(u128::from(self.numerator), u128::from(self.denominator))
                as u32;
        Self {
            numerator: self.numerator / divisor,
            denominator: self.denominator / divisor,
        }
    }
}

impl PartialEq for FrameRate {
    fn eq(&self, other: &Self) -> bool {
        if self.denominator == 0 || other.denominator == 0 {
            return self.numerator == other.numerator && self.denominator == other.denominator;
        }

        u64::from(self.numerator) * u64::from(other.denominator)
            == u64::from(other.numerator) * u64::from(self.denominator)
    }
}

impl Hash for FrameRate {
    fn hash<H: Hasher>(&self, state: &mut H) {
        let reduced = self.reduced();
        reduced.numerator.hash(state);
        reduced.denominator.hash(state);
    }
}

impl PartialOrd for FrameRate {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        if self == other {
            return Some(Ordering::Equal);
        }
        if self.denominator == 0 || other.denominator == 0 {
            return None;
        }

        let left = u64::from(self.numerator) * u64::from(other.denominator);
        let right = u64::from(other.numerator) * u64::from(self.denominator);
        Some(left.cmp(&right))
    }
}

impl From<Fraction> for FrameRate {
    fn from(fraction: Fraction) -> Self {
        Self {
            numerator: fraction.num,
            denominator: fraction.denom,
        }
        .reduced()
    }
}

fn valid_frame_rate_fraction(value: Fraction) -> bool {
    value.num != 0 && value.denom != 0
}

fn greatest_common_divisor(mut left: u128, mut right: u128) -> u128 {
    while right != 0 {
        (left, right) = (right, left % right);
    }
    left
}

fn fraction_multiple(step: Fraction, multiple: u128) -> Option<Fraction> {
    let numerator = u128::from(step.num) * multiple;
    let denominator = u128::from(step.denom);
    let divisor = greatest_common_divisor(numerator, denominator);

    Some(Fraction {
        num: (numerator / divisor)
            .try_into()
            .inspect_err(|error| debug!(%error, ?step, multiple, "derived frame rate exceeds u32"))
            .ok()?,
        denom: (denominator / divisor).try_into().ok()?,
    })
}

fn aligned_fraction_bounds(
    min: Fraction,
    max: Fraction,
    step: Fraction,
) -> Option<(Fraction, Fraction)> {
    let min_numerator = u128::from(min.num) * u128::from(step.denom);
    let min_denominator = u128::from(min.denom) * u128::from(step.num);
    let max_numerator = u128::from(max.num) * u128::from(step.denom);
    let max_denominator = u128::from(max.denom) * u128::from(step.num);
    let min_multiple = min_numerator.div_ceil(min_denominator);
    let max_multiple = max_numerator / max_denominator;

    if min_multiple > max_multiple {
        return None;
    }

    Some((
        fraction_multiple(step, min_multiple)?,
        fraction_multiple(step, max_multiple)?,
    ))
}

fn fraction_matches_step(
    requested: Fraction,
    min: Fraction,
    max: Fraction,
    step: Fraction,
) -> bool {
    let requested_rate = FrameRate::from(requested);
    if requested_rate < FrameRate::from(min) || requested_rate > FrameRate::from(max) {
        return false;
    }

    let step_numerator = u64::from(requested.num) * u64::from(step.denom);
    let step_denominator = u64::from(requested.denom) * u64::from(step.num);

    step_numerator.is_multiple_of(step_denominator)
}

fn fractions_from_range(
    default: Fraction,
    min: Fraction,
    max: Fraction,
    requested: Option<Fraction>,
) -> Vec<Fraction> {
    let Some(requested) = requested else {
        return vec![default, min, max];
    };

    let requested_rate = FrameRate::from(requested);
    if requested_rate < FrameRate::from(min) || requested_rate > FrameRate::from(max) {
        return Vec::new();
    }

    vec![requested]
}

fn fractions_from_step(
    default: Fraction,
    min: Fraction,
    max: Fraction,
    step: Fraction,
    requested: Option<Fraction>,
) -> Vec<Fraction> {
    if let Some(requested) = requested {
        if fraction_matches_step(requested, min, max, step) {
            return vec![requested];
        }
        return Vec::new();
    }

    let mut fractions = vec![default];
    if let Some((aligned_min, aligned_max)) = aligned_fraction_bounds(min, max, step) {
        fractions.extend([aligned_min, aligned_max]);
    }
    fractions
}

pub(super) fn fraction_choice_from_value(value: Value) -> Option<ChoiceEnum<Fraction>> {
    match value {
        Value::Fraction(fraction) => Some(ChoiceEnum::None(fraction)),
        Value::Choice(ChoiceValue::Fraction(Choice(_, choice))) => Some(choice),
        _ => None,
    }
}

fn fraction_candidates(choice: ChoiceEnum<Fraction>, requested: Option<Fraction>) -> Vec<Fraction> {
    match choice {
        ChoiceEnum::None(fraction) => vec![fraction],
        ChoiceEnum::Enum {
            default,
            alternatives,
        } => {
            let mut fractions = vec![default];
            fractions.extend(alternatives);
            fractions
        }
        ChoiceEnum::Range { default, min, max } => {
            fractions_from_range(default, min, max, requested)
        }
        ChoiceEnum::Step {
            default,
            min,
            max,
            step,
        } => fractions_from_step(default, min, max, step, requested),
        _ => Vec::new(),
    }
}

pub(super) fn select_frame_rates(
    choice: ChoiceEnum<Fraction>,
    requested: Option<&FrameRate>,
) -> HashSet<FrameRate> {
    let requested_fraction = requested.map(|requested| Fraction {
        num: requested.numerator,
        denom: requested.denominator,
    });
    if requested_fraction.is_some_and(|fraction| !valid_frame_rate_fraction(fraction)) {
        return HashSet::new();
    }

    let choice = match choice {
        ChoiceEnum::Range { min, max, .. }
            if requested_fraction.is_some()
                && (!valid_frame_rate_fraction(min) || !valid_frame_rate_fraction(max)) =>
        {
            return HashSet::new();
        }
        ChoiceEnum::Step {
            default,
            min,
            max,
            step,
        } if !valid_frame_rate_fraction(min)
            || !valid_frame_rate_fraction(max)
            || !valid_frame_rate_fraction(step) =>
        {
            if requested_fraction.is_some() {
                return HashSet::new();
            }
            ChoiceEnum::None(default)
        }
        choice => choice,
    };
    let fractions = fraction_candidates(choice, requested_fraction);

    let mut frame_rates = HashSet::new();
    for fraction in fractions {
        if !valid_frame_rate_fraction(fraction) {
            continue;
        }

        let frame_rate = FrameRate::from(fraction);
        if requested.is_some_and(|requested| requested != &frame_rate) {
            continue;
        }

        frame_rates.insert(frame_rate);
    }
    frame_rates
}
