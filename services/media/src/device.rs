// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire::{self as pw, registry::GlobalObject, spa::utils::dict::DictRef};
use thiserror::Error;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DeviceType {
    Camera,
}

impl DeviceType {
    pub(crate) fn media_class(self) -> &'static str {
        match self {
            Self::Camera => "Video/Source",
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Device {
    pub node_id: u32,
    pub object_serial: u64,
    pub name: String,
    pub device_type: DeviceType,
}

#[derive(Debug, Error, Eq, PartialEq)]
pub enum DeviceError {
    #[error("unsupported PipeWire device node")]
    UnsupportedNode,
    #[error("device node missing object serial")]
    MissingObjectSerial,
    #[error("device node has invalid object serial: {0}")]
    InvalidObjectSerial(String),
}

impl Device {
    pub fn try_from_global_object<P>(global_obj: &GlobalObject<P>) -> Result<Self, DeviceError>
    where
        P: AsRef<DictRef>,
    {
        Ok(Self {
            node_id: global_obj.id,
            device_type: get_object_device_type(global_obj)?,
            object_serial: get_object_serial(global_obj)?,
            name: global_obj
                .props
                .as_ref()
                .and_then(|props| {
                    props
                        .as_ref()
                        .get(&pw::keys::NODE_NICK)
                        .or_else(|| props.as_ref().get(&pw::keys::NODE_DESCRIPTION))
                        .or_else(|| props.as_ref().get(&pw::keys::NODE_NAME))
                })
                .unwrap_or("")
                .to_string(),
        })
    }
}

fn get_object_device_type<P>(global_obj: &GlobalObject<P>) -> Result<DeviceType, DeviceError>
where
    P: AsRef<DictRef>,
{
    if global_obj.type_ != pw::types::ObjectType::Node {
        return Err(DeviceError::UnsupportedNode);
    }
    let media_class = global_obj
        .props
        .as_ref()
        .and_then(|props| props.as_ref().get(&pw::keys::MEDIA_CLASS))
        .ok_or(DeviceError::UnsupportedNode)?;

    match media_class {
        "Video/Source" => Ok(DeviceType::Camera),
        _ => Err(DeviceError::UnsupportedNode),
    }
}

fn get_object_serial<P>(global_obj: &GlobalObject<P>) -> Result<u64, DeviceError>
where
    P: AsRef<DictRef>,
{
    let serial = global_obj
        .props
        .as_ref()
        .and_then(|props| props.as_ref().get(&pw::keys::OBJECT_SERIAL))
        .ok_or(DeviceError::MissingObjectSerial)?;

    serial
        .parse()
        .map_err(|_| DeviceError::InvalidObjectSerial(serial.to_string()))
}
