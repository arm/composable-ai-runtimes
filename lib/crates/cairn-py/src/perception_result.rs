// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use cairn::perception_service::result as model;
use pyo3::exceptions::PyValueError;
use pyo3::types::{PyAnyMethods, PyBytes, PyBytesMethods, PyModule, PyModuleMethods, PyTuple};
use pyo3::{Bound, Py, PyAny, PyErr, PyResult, Python, pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use pyo3_stub_gen::runtime::PyModuleTypeAliasExt;

use crate::perception_result_models::{
    PyBoxDetections, PyClassifications, PyFrameContext, PyObjectEmbeddings, PyObjectTracks,
    PyPerformanceOverlay, PyPoseEstimations, PySegmentationMasks, PyTrackTraces,
};

macro_rules! error_member {
    ($name:literal, $type:ty, $doc:literal) => {
        pyo3_stub_gen::type_info::MemberInfo {
            name: $name,
            r#type: || <$type as pyo3_stub_gen::PyStubType>::type_output(),
            doc: $doc,
            default: None,
            deprecated: None,
        }
    };
}

macro_rules! define_error {
    ($name:ident, $base:ty, $doc:literal, [$($getter:expr),* $(,)?]) => {
        pyo3::create_exception!(cairn.perception, $name, $base, $doc);
        impl pyo3_stub_gen::PyStubType for $name {
            fn type_output() -> pyo3_stub_gen::TypeInfo {
                pyo3_stub_gen::TypeInfo::locally_defined(
                    stringify!($name),
                    pyo3_stub_gen::ModuleRef::Named("cairn.perception".to_string()),
                )
            }
        }
        pyo3_stub_gen::inventory::submit! {
            pyo3_stub_gen::type_info::PyClassInfo {
                pyclass_name: stringify!($name),
                struct_id: std::any::TypeId::of::<$name>,
                getters: &[$($getter),*],
                setters: &[],
                module: Some("cairn.perception"),
                doc: $doc,
                bases: &[|| <$base as pyo3_stub_gen::PyStubType>::type_output()],
                has_eq: false,
                has_ord: false,
                has_hash: false,
                has_str: false,
                subclass: true,
            }
        }
    };
}

define_error!(
    PerceptionResultError,
    PyValueError,
    "Base class for Perception result payload decoding errors.",
    [error_member!(
        "packet",
        Py<PyBytes>,
        "Original result packet bytes."
    )]
);
define_error!(
    InvalidEnvelopeError,
    PerceptionResultError,
    "Raised when a result packet is not a valid Perception envelope.",
    []
);
define_error!(
    ProducerIdentityError,
    PerceptionResultError,
    "Base class for incompatible Perception producer identity errors.",
    [
        error_member!(
            "received_sdk_name",
            Option<String>,
            "Producer SDK name recorded in the packet."
        ),
        error_member!(
            "received_sdk_version",
            Option<String>,
            "Producer SDK version recorded in the packet."
        ),
        error_member!(
            "received_schema_digest",
            Option<String>,
            "Producer schema digest recorded in the packet."
        ),
    ]
);
define_error!(
    MissingProducerIdentityError,
    ProducerIdentityError,
    "Raised when required producer identity fields are missing.",
    []
);
define_error!(
    MalformedProducerIdentityError,
    ProducerIdentityError,
    "Raised when a producer identity field is malformed.",
    []
);
define_error!(
    UnexpectedProducerError,
    ProducerIdentityError,
    "Raised when a packet was produced by an unexpected SDK.",
    []
);
define_error!(
    UnsupportedProducerVersionError,
    ProducerIdentityError,
    "Raised when the producer uses an unsupported Perception SDK version.",
    []
);
define_error!(
    IncompatibleProducerSchemaError,
    ProducerIdentityError,
    "Raised when the producer schema set differs from the supported schema set.",
    []
);
define_error!(
    UnsupportedPayloadSchemaVersionError,
    PerceptionResultError,
    "Raised when a payload uses an unsupported schema major version.",
    [
        error_member!(
            "payload_type",
            String,
            "Payload schema type with an unsupported version."
        ),
        error_member!("schema_major", u16, "Unsupported schema major version."),
        error_member!(
            "schema_minor",
            u16,
            "Schema minor version received in the packet."
        ),
        error_member!(
            "supported_schema_major",
            u16,
            "Schema major version supported by this decoder."
        ),
    ]
);

/// Application-defined opaque payload using OPK's reserved external-ID range.
#[gen_stub_pyclass]
#[pyclass(frozen, get_all, module = "cairn.perception", name = "ExternalPayload")]
struct PyExternalPayload {
    /// Numeric external key from the wire envelope.
    id: u64,
    /// Unmodified payload bytes.
    bytes: Py<PyBytes>,
}

/// Raw payload data whose identifier is not owned by the installed OPK SDK.
#[gen_stub_pyclass]
#[pyclass(frozen, get_all, module = "cairn.perception", name = "UnknownPayload")]
struct PyUnknownPayload {
    /// Numeric payload identifier from the wire envelope.
    id: u64,
    /// Unmodified payload bytes.
    bytes: Py<PyBytes>,
}

/// Raw data and diagnostics for a malformed recognized payload.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "MalformedKnownPayload"
)]
struct PyMalformedKnownPayload {
    /// Numeric payload identifier from the packet.
    id: u64,
    /// Schema type registered for the identifier.
    expected_type: String,
    /// Unmodified payload bytes.
    bytes: Py<PyBytes>,
    /// Diagnostic from the registered payload decoder.
    detail: String,
}

/// A decoded Perception result containing Cairn-owned payload entries.
#[gen_stub_pyclass]
#[pyclass(frozen, module = "cairn.perception", name = "PerceptionResult")]
pub struct PyPerceptionResult {
    entries: Py<PyTuple>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyPerceptionResult {
    /// Decode a raw FLWD result packet once with the Rust decoder.
    #[staticmethod]
    fn decode(py: Python<'_>, payload: &Bound<'_, PyBytes>) -> PyResult<Self> {
        let result = match model::PerceptionResult::decode(payload.as_bytes()) {
            Ok(result) => result,
            Err(error) => return Err(result_error(py, error)?),
        };
        let entries = result
            .into_entries()
            .into_iter()
            .map(|entry| bind_entry(py, entry))
            .collect::<PyResult<Vec<_>>>()?;
        let entries = PyTuple::new(py, entries)?;
        Ok(Self {
            entries: entries.unbind(),
        })
    }

    /// Payload entries in their original packet order.
    #[getter]
    #[gen_stub(override_return_type(type_repr = "tuple[PerceptionPayload, ...]"))]
    fn entries(&self, py: Python<'_>) -> Py<PyTuple> {
        self.entries.clone_ref(py)
    }
}

fn bind_entry(py: Python<'_>, entry: model::PerceptionPayload) -> PyResult<Py<PyAny>> {
    match entry {
        model::PerceptionPayload::BoxDetections(value) => {
            Ok(Py::new(py, PyBoxDetections::from(value))?.into_any())
        }
        model::PerceptionPayload::Classifications(value) => {
            Ok(Py::new(py, PyClassifications::from(value))?.into_any())
        }
        model::PerceptionPayload::FrameContext(value) => {
            Ok(Py::new(py, PyFrameContext::from(value))?.into_any())
        }
        model::PerceptionPayload::ObjectEmbeddings(value) => {
            Ok(Py::new(py, PyObjectEmbeddings::from(value))?.into_any())
        }
        model::PerceptionPayload::ObjectTracks(value) => {
            Ok(Py::new(py, PyObjectTracks::from(value))?.into_any())
        }
        model::PerceptionPayload::PerformanceOverlay(value) => {
            Ok(Py::new(py, PyPerformanceOverlay::from(value))?.into_any())
        }
        model::PerceptionPayload::PoseEstimations(value) => {
            Ok(Py::new(py, PyPoseEstimations::from(value))?.into_any())
        }
        model::PerceptionPayload::SegmentationMasks(value) => {
            Ok(Py::new(py, PySegmentationMasks::from(value))?.into_any())
        }
        model::PerceptionPayload::TrackTraces(value) => {
            Ok(Py::new(py, PyTrackTraces::from(value))?.into_any())
        }
        model::PerceptionPayload::External(value) => Ok(Py::new(
            py,
            PyExternalPayload {
                id: value.id,
                bytes: PyBytes::new(py, &value.bytes).unbind(),
            },
        )?
        .into_any()),
        model::PerceptionPayload::Unknown(value) => Ok(Py::new(
            py,
            PyUnknownPayload {
                id: value.id,
                bytes: PyBytes::new(py, &value.bytes).unbind(),
            },
        )?
        .into_any()),
        model::PerceptionPayload::MalformedKnown(value) => Ok(Py::new(
            py,
            PyMalformedKnownPayload {
                id: value.id,
                expected_type: value.expected_type,
                bytes: PyBytes::new(py, &value.bytes).unbind(),
                detail: value.detail,
            },
        )?
        .into_any()),
    }
}

fn result_error(py: Python<'_>, error: model::PerceptionResultError) -> PyResult<PyErr> {
    let message = error.to_string();
    let packet = error.packet().to_vec();
    let exception = match &error {
        model::PerceptionResultError::InvalidEnvelope { .. } => {
            InvalidEnvelopeError::new_err(message)
        }
        model::PerceptionResultError::MissingProducerIdentity { .. } => {
            MissingProducerIdentityError::new_err(message)
        }
        model::PerceptionResultError::MalformedProducerIdentity { .. } => {
            MalformedProducerIdentityError::new_err(message)
        }
        model::PerceptionResultError::UnexpectedProducer { .. } => {
            UnexpectedProducerError::new_err(message)
        }
        model::PerceptionResultError::UnsupportedProducerVersion { .. } => {
            UnsupportedProducerVersionError::new_err(message)
        }
        model::PerceptionResultError::IncompatibleProducerSchema { .. } => {
            IncompatibleProducerSchemaError::new_err(message)
        }
        model::PerceptionResultError::UnsupportedPayloadSchemaVersion {
            payload_type,
            schema_major,
            schema_minor,
            supported_schema_major,
            ..
        } => {
            let exception = UnsupportedPayloadSchemaVersionError::new_err(message);
            let value = exception.value(py);
            value.setattr("payload_type", payload_type)?;
            value.setattr("schema_major", *schema_major)?;
            value.setattr("schema_minor", *schema_minor)?;
            value.setattr("supported_schema_major", *supported_schema_major)?;
            exception
        }
    };
    let value = exception.value(py);
    value.setattr("packet", PyBytes::new(py, &packet))?;
    if exception.is_instance_of::<ProducerIdentityError>(py) {
        let (received_sdk_name, received_sdk_version, received_schema_digest) =
            match error.decoded_envelope_context() {
                Some(context) => (
                    Some(context.received_sdk_name().to_owned()),
                    Some(context.received_sdk_version().to_owned()),
                    Some(context.received_schema_digest().to_owned()),
                ),
                None => (None, None, None),
            };
        value.setattr("received_sdk_name", received_sdk_name)?;
        value.setattr("received_sdk_version", received_sdk_version)?;
        value.setattr("received_schema_digest", received_schema_digest)?;
    }
    Ok(exception)
}

pyo3_stub_gen::type_alias!(
    "cairn.perception",
    PerceptionPayload = PyBoxDetections
        | PyClassifications
        | PyFrameContext
        | PyObjectEmbeddings
        | PyObjectTracks
        | PyPerformanceOverlay
        | PyPoseEstimations
        | PySegmentationMasks
        | PyTrackTraces
        | PyExternalPayload
        | PyUnknownPayload
        | PyMalformedKnownPayload,
    "A decoded or preserved Perception result entry."
);

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add(
        "PerceptionResultError",
        module.py().get_type::<PerceptionResultError>(),
    )?;
    module.add(
        "InvalidEnvelopeError",
        module.py().get_type::<InvalidEnvelopeError>(),
    )?;
    module.add(
        "ProducerIdentityError",
        module.py().get_type::<ProducerIdentityError>(),
    )?;
    module.add(
        "MissingProducerIdentityError",
        module.py().get_type::<MissingProducerIdentityError>(),
    )?;
    module.add(
        "MalformedProducerIdentityError",
        module.py().get_type::<MalformedProducerIdentityError>(),
    )?;
    module.add(
        "UnexpectedProducerError",
        module.py().get_type::<UnexpectedProducerError>(),
    )?;
    module.add(
        "UnsupportedProducerVersionError",
        module.py().get_type::<UnsupportedProducerVersionError>(),
    )?;
    module.add(
        "IncompatibleProducerSchemaError",
        module.py().get_type::<IncompatibleProducerSchemaError>(),
    )?;
    module.add(
        "UnsupportedPayloadSchemaVersionError",
        module
            .py()
            .get_type::<UnsupportedPayloadSchemaVersionError>(),
    )?;
    module.add_class::<PyPerceptionResult>()?;
    crate::perception_result_models::register(module)?;
    module.add_class::<PyExternalPayload>()?;
    module.add_class::<PyUnknownPayload>()?;
    module.add_class::<PyMalformedKnownPayload>()?;
    module.add_type_alias::<PerceptionPayload>()?;

    Ok(())
}
