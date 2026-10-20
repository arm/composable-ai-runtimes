// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::sync::Arc;

use cairn::perception_service::output::DebugOutput as RustDebugOutput;
use cairn::perception_service::workflow::PerceptionWorkflow as RustPerceptionWorkflow;
use cairn::perception_service::{
    DebugPorts as RustDebugPorts, PerceptionService as RustPerceptionService,
    PerceptionServiceError as RustPerceptionServiceError,
    PerceptionSession as RustPerceptionSession, ResolvedStage as RustResolvedStage,
    ResolvedStageRole, ServiceInfo as RustServiceInfo, SessionSnapshot as RustSessionSnapshot,
    SessionState as RustSessionState, SessionStatus as RustSessionStatus,
    SessionTopics as RustSessionTopics, StatusInfo as RustStatusInfo,
    ValidationIssue as RustValidationIssue, ValidationResult as RustValidationResult,
    ValidationSeverity,
};
use pyo3::exceptions::PyException;
use pyo3::types::{PyAnyMethods, PyList, PyModule, PyModuleMethods};
use pyo3::{Bound, Py, PyAny, PyErr, PyResult, Python, pyclass, pymethods};
use pyo3_async_runtimes::tokio as tokio_runtime;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyclass_enum, gen_stub_pymethods};
use tokio::sync::Mutex;

use crate::camera_types::PyStreamConfiguration;

macro_rules! create_perception_exception {
    ($name:ident, $base:ty, $doc:literal) => {
        create_perception_exception!($name, $base, $doc, &[]);
    };
    ($name:ident, $base:ty, $doc:literal, $getters:expr) => {
        pyo3::create_exception!(cairn, $name, $base, $doc);

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
                getters: $getters,
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

create_perception_exception!(
    PerceptionError,
    PyException,
    "Raised when a Perception service request fails."
);
create_perception_exception!(
    PerceptionDeploymentError,
    PerceptionError,
    "Raised when a Perception workflow cannot be deployed."
);
create_perception_exception!(
    DeploymentValidationError,
    PerceptionDeploymentError,
    "Raised when a Perception workflow is rejected.",
    &[pyo3_stub_gen::type_info::MemberInfo {
        name: "issues",
        r#type: || <Option<Vec<PyValidationIssue>> as pyo3_stub_gen::PyStubType>::type_output(),
        doc: "Validation errors that caused the deployment rejection.",
        default: None,
        deprecated: None,
    }]
);

/// Ports exposed by a Perception workflow's debug output.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    module = "cairn.perception",
    name = "DebugOutput",
    skip_from_py_object
)]
#[derive(Clone, Copy)]
pub struct PyDebugOutput(RustDebugOutput);

#[gen_stub_pymethods]
#[pymethods]
impl PyDebugOutput {
    /// Configure debug output ports.
    ///
    /// Set a port to 0 to use its default: HTTP 9999, WebSocket 8000, control 8001.
    /// Read resolved ports from the deployed session's ``debug_endpoint``.
    #[new]
    #[pyo3(signature = (http_port=0, ws_port=0, ctrl_port=0))]
    fn new(http_port: u32, ws_port: u32, ctrl_port: u32) -> Self {
        Self(RustDebugOutput {
            http_port,
            ws_port,
            ctrl_port,
        })
    }

    /// HTTP port for the debug output.
    #[getter]
    fn http_port(&self) -> u32 {
        self.0.http_port
    }

    /// WebSocket port for the debug output.
    #[getter]
    fn ws_port(&self) -> u32 {
        self.0.ws_port
    }

    /// Control port for the debug output.
    #[getter]
    fn ctrl_port(&self) -> u32 {
        self.0.ctrl_port
    }
}

/// Identifies an inference stage added to a Perception workflow.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "StageHandle",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PyStageHandle {
    /// Generated stage identifier.
    id: String,
    /// User-facing stage name.
    name: String,
}

/// Version and capability information reported by the Perception service.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "ServiceInfo",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PyServiceInfo {
    /// API version implemented by the service.
    api_version: String,
    /// Version of the running service.
    service_version: String,
    /// Whether active sessions persist when the service restarts.
    sessions_survive_restart: bool,
}

impl From<RustServiceInfo> for PyServiceInfo {
    fn from(info: RustServiceInfo) -> Self {
        Self {
            api_version: info.api_version,
            service_version: info.service_version,
            sessions_survive_restart: info.sessions_survive_restart,
        }
    }
}

/// A problem found while validating a Perception workflow.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "ValidationIssue",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PyValidationIssue {
    /// Issue severity.
    severity: String,
    /// Machine-readable issue code.
    code: String,
    /// Human-readable issue description.
    message: String,
    /// Path to the invalid workflow field, when available.
    field_path: Option<String>,
    /// ID of the affected stage, when available.
    stage_id: Option<String>,
}

impl From<RustValidationIssue> for PyValidationIssue {
    fn from(issue: RustValidationIssue) -> Self {
        Self {
            severity: validation_severity_name(issue.severity),
            code: issue.code,
            message: issue.message,
            field_path: issue.field_path,
            stage_id: issue.stage_id,
        }
    }
}

/// A workflow stage resolved by the Perception service.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "ResolvedStage",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PyResolvedStage {
    /// Service-assigned stage identifier.
    id: String,
    /// User-facing stage name.
    name: String,
    /// Role performed by the stage.
    role: String,
    /// Whether the running stage can be enabled or disabled.
    controllable: bool,
    /// Model used by the stage, when applicable.
    model_id: Option<String>,
}

impl From<RustResolvedStage> for PyResolvedStage {
    fn from(stage: RustResolvedStage) -> Self {
        Self {
            id: stage.id,
            name: stage.name,
            role: resolved_stage_role_name(stage.role),
            controllable: stage.controllable,
            model_id: stage.model_id,
        }
    }
}

/// Result returned after validating a Perception workflow.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "ValidationResult",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PyValidationResult {
    /// Whether the workflow is valid.
    valid: bool,
    /// Validation errors that prevent deployment.
    errors: Vec<PyValidationIssue>,
    /// Validation warnings that do not prevent deployment.
    warnings: Vec<PyValidationIssue>,
    /// Stages resolved from the workflow specification.
    stages: Vec<PyResolvedStage>,
}

impl From<RustValidationResult> for PyValidationResult {
    fn from(result: RustValidationResult) -> Self {
        let (errors, warnings): (Vec<_>, Vec<_>) = result
            .issues
            .into_iter()
            .partition(|issue| issue.severity == ValidationSeverity::Error);
        Self {
            valid: result.valid,
            errors: errors.into_iter().map(PyValidationIssue::from).collect(),
            warnings: warnings.into_iter().map(PyValidationIssue::from).collect(),
            stages: result
                .stages
                .into_iter()
                .map(PyResolvedStage::from)
                .collect(),
        }
    }
}

/// Ports allocated to a deployed session's debug output.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "DebugPorts",
    skip_from_py_object
)]
#[derive(Clone, Copy)]
pub struct PyDebugPorts {
    /// HTTP port for the debug output.
    http_port: u32,
    /// WebSocket port for the debug output.
    ws_port: u32,
    /// Control port for the debug output.
    ctrl_port: u32,
}

impl From<RustDebugPorts> for PyDebugPorts {
    fn from(ports: RustDebugPorts) -> Self {
        Self {
            http_port: ports.http_port,
            ws_port: ports.ws_port,
            ctrl_port: ports.ctrl_port,
        }
    }
}

/// Opaque notification topics allocated to a deployed session.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "SessionTopics",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PySessionTopics {
    /// Topic carrying inference results, when allocated.
    results: Option<String>,
    /// Topic carrying session lifecycle events, when allocated.
    /// This is `None` when the workflow was created with
    /// `output_events=False`. Check that it is not `None` before passing it to
    /// `NotificationService.subscribe()`.
    events: Option<String>,
}

impl From<RustSessionTopics> for PySessionTopics {
    fn from(topics: RustSessionTopics) -> Self {
        Self {
            results: topics.results,
            events: topics.events,
        }
    }
}

/// Additional information reported with a session status.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "StatusInfo",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PyStatusInfo {
    /// Machine-readable status code.
    code: String,
    /// Human-readable status message.
    message: String,
}

impl From<RustStatusInfo> for PyStatusInfo {
    fn from(info: RustStatusInfo) -> Self {
        Self {
            code: info.code,
            message: info.message,
        }
    }
}

/// Lifecycle state of a Perception session.
#[gen_stub_pyclass_enum]
#[pyclass(
    frozen,
    eq,
    hash,
    module = "cairn.perception",
    name = "SessionState",
    skip_from_py_object
)]
#[repr(i32)]
#[derive(Clone, PartialEq, Hash)]
pub enum PySessionState {
    /// The service did not specify a lifecycle state.
    Unspecified = 0,
    /// The session is starting.
    Starting = 1,
    /// The session is running.
    Running = 2,
    /// The session is stopping.
    Stopping = 3,
    /// The session has stopped.
    Stopped = 4,
    /// The session failed.
    Failed = 5,
    /// A lifecycle state not recognized by this SDK version.
    /// The original numeric value is not exposed by the Python binding.
    Unknown = -1,
}

impl From<RustSessionState> for PySessionState {
    fn from(state: RustSessionState) -> Self {
        match state {
            RustSessionState::Unspecified => Self::Unspecified,
            RustSessionState::Starting => Self::Starting,
            RustSessionState::Running => Self::Running,
            RustSessionState::Stopping => Self::Stopping,
            RustSessionState::Stopped => Self::Stopped,
            RustSessionState::Failed => Self::Failed,
            RustSessionState::Unknown(_) => Self::Unknown,
        }
    }
}

/// Current lifecycle status of a Perception session.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "SessionStatus",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PySessionStatus {
    /// Current lifecycle state.
    state: PySessionState,
    /// Additional status information, when supplied by the service.
    info: Option<PyStatusInfo>,
}

impl From<RustSessionStatus> for PySessionStatus {
    fn from(status: RustSessionStatus) -> Self {
        Self {
            state: PySessionState::from(status.state),
            info: status.info.map(PyStatusInfo::from),
        }
    }
}

/// Snapshot of a Perception session's current state.
#[gen_stub_pyclass]
#[pyclass(
    frozen,
    get_all,
    module = "cairn.perception",
    name = "SessionSnapshot",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PySessionSnapshot {
    /// Current session status.
    status: PySessionStatus,
    /// IDs of stages that are currently disabled.
    disabled_stage_ids: Vec<String>,
}

impl From<RustSessionSnapshot> for PySessionSnapshot {
    fn from(snapshot: RustSessionSnapshot) -> Self {
        Self {
            status: PySessionStatus::from(snapshot.status),
            disabled_stage_ids: snapshot.disabled_stage_ids,
        }
    }
}

/// Handle to a deployed Perception session.
#[gen_stub_pyclass]
#[pyclass(frozen, module = "cairn.perception", name = "PerceptionSession")]
pub struct PyPerceptionSession(RustPerceptionSession);

#[gen_stub_pymethods]
#[pymethods]
impl PyPerceptionSession {
    /// Remote session identifier.
    #[getter]
    fn id(&self) -> &str {
        self.0.id()
    }

    /// Deployed workflow name.
    #[getter]
    fn workflow_name(&self) -> &str {
        self.0.workflow_name()
    }

    /// Resolved stages in this session.
    #[getter]
    fn stages(&self) -> Vec<PyResolvedStage> {
        self.0
            .stages()
            .iter()
            .cloned()
            .map(PyResolvedStage::from)
            .collect()
    }

    /// Allocated debug ports, when debug output is enabled.
    #[getter]
    fn debug_endpoint(&self) -> Option<PyDebugPorts> {
        self.0.debug_endpoint().copied().map(PyDebugPorts::from)
    }

    /// Opaque notification topics allocated to this session.
    /// Check that an optional topic is not `None` before passing it to
    /// `NotificationService.subscribe()`.
    #[getter]
    fn topics(&self) -> PySessionTopics {
        PySessionTopics::from(self.0.topics().clone())
    }

    /// Request that an inference stage in this session be disabled.
    /// Pass an ID from ``workflow.infer(...).id`` or ``session.stages``, not a
    /// model ID or display name. Raises ``PerceptionError`` if the request fails.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[None]",
        imports = ("collections.abc",)
    ))]
    fn disable_stage<'py>(&self, py: Python<'py>, stage_id: String) -> PyResult<Bound<'py, PyAny>> {
        let session = self.0.clone();
        tokio_runtime::future_into_py(py, async move {
            session
                .disable_stage(&stage_id)
                .await
                .map_err(perception_error)?;
            Ok(Python::attach(|py| py.None()))
        })
    }

    /// Request that an inference stage in this session be enabled.
    /// Pass an ID from ``workflow.infer(...).id`` or ``session.stages``, not a
    /// model ID or display name. Raises ``PerceptionError`` if the request fails.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[None]",
        imports = ("collections.abc",)
    ))]
    fn enable_stage<'py>(&self, py: Python<'py>, stage_id: String) -> PyResult<Bound<'py, PyAny>> {
        let session = self.0.clone();
        tokio_runtime::future_into_py(py, async move {
            session
                .enable_stage(&stage_id)
                .await
                .map_err(perception_error)?;
            Ok(Python::attach(|py| py.None()))
        })
    }

    /// Return the current snapshot of this remote session.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[SessionSnapshot]",
        imports = ("collections.abc",)
    ))]
    fn get_status<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let session = self.0.clone();
        tokio_runtime::future_into_py(py, async move {
            let snapshot = session.get_status().await.map_err(perception_error)?;
            Python::attach(|py| Py::new(py, PySessionSnapshot::from(snapshot)))
        })
    }

    /// Request shutdown of this session. Stopping an already stopped session has no effect.
    ///
    /// Await this explicitly when finished. Raises ``PerceptionError`` if the request fails.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[None]",
        imports = ("collections.abc",)
    ))]
    fn stop<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let session = self.0.clone();
        tokio_runtime::future_into_py(py, async move {
            session.stop().await.map_err(perception_error)?;
            Ok(())
        })
    }
}

/// Build a workflow locally, then submit it for validation or deployment.
///
/// Start with a camera-discovered stream configuration, add inference stages, then
/// await ``PerceptionService.validate()`` or ``deploy()``. Models must already be
/// registered on the service.
#[gen_stub_pyclass]
#[pyclass(
    module = "cairn.perception",
    name = "PerceptionWorkflow",
    skip_from_py_object
)]
#[derive(Clone)]
pub struct PyPerceptionWorkflow(RustPerceptionWorkflow);

#[gen_stub_pymethods]
#[pymethods]
impl PyPerceptionWorkflow {
    /// Create a workflow with the given name and camera stream configuration.
    /// Pass `output_events=False` to disable lifecycle-event publication. The
    /// deployed session's `topics.events` is then `None`.
    #[new]
    #[pyo3(signature = (name, source_configuration, *, output_events = true))]
    fn new(
        name: String,
        source_configuration: &PyStreamConfiguration,
        output_events: bool,
    ) -> Self {
        let mut workflow = RustPerceptionWorkflow::new(name, source_configuration.0.clone());
        workflow.set_output_events(output_events);
        Self(workflow)
    }

    /// Add an inference stage using a model registered on the service.
    ///
    /// ``model_id`` is the model package directory name, not a local file path.
    fn infer(&mut self, name: String, model_id: String) -> PyStageHandle {
        let stage = self.0.infer(name, model_id);
        PyStageHandle {
            id: stage.id,
            name: stage.name,
        }
    }

    /// Enable debug output, replacing any previous debug output configuration.
    fn output(&mut self, output: &PyDebugOutput) {
        self.0.set_debug_output(output.0);
    }
}

/// Asynchronous client for the Cairn Perception service.
#[gen_stub_pyclass]
#[pyclass(module = "cairn.perception", name = "PerceptionService")]
pub struct PyPerceptionService(Arc<Mutex<RustPerceptionService>>);

#[gen_stub_pymethods]
#[pymethods]
impl PyPerceptionService {
    /// Connect to the Perception service.
    ///
    /// Await this method. ``None`` uses ``http://127.0.0.1:50053``.
    /// Connection failures raise ``PerceptionError``.
    #[staticmethod]
    #[pyo3(signature = (endpoint=None))]
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[PerceptionService]",
        imports = ("collections.abc",)
    ))]
    fn connect<'py>(py: Python<'py>, endpoint: Option<String>) -> PyResult<Bound<'py, PyAny>> {
        tokio_runtime::future_into_py(py, async move {
            let service = RustPerceptionService::new(endpoint)
                .await
                .map_err(perception_error)?;
            Python::attach(|py| Py::new(py, Self(Arc::new(Mutex::new(service)))))
        })
    }

    /// Return version and capability information from the connected service.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[ServiceInfo]",
        imports = ("collections.abc",)
    ))]
    fn get_service_info<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let service = Arc::clone(&self.0);
        tokio_runtime::future_into_py(py, async move {
            let info = service
                .lock()
                .await
                .get_service_info()
                .await
                .map_err(perception_error)?;
            Python::attach(|py| Py::new(py, PyServiceInfo::from(info)))
        })
    }

    /// Return the session identified by ``session_id``. If the ID is unknown,
    /// awaiting this method raises ``PerceptionError`` with a ``NotFound`` service error.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[PerceptionSession]",
        imports = ("collections.abc",)
    ))]
    fn get_session<'py>(&self, py: Python<'py>, session_id: String) -> PyResult<Bound<'py, PyAny>> {
        let service = Arc::clone(&self.0);
        tokio_runtime::future_into_py(py, async move {
            let session = service
                .lock()
                .await
                .get_session(session_id)
                .await
                .map_err(perception_error)?;
            Python::attach(|py| Py::new(py, PyPerceptionSession(session)))
        })
    }

    /// Validate a workflow without deploying it.
    ///
    /// An invalid workflow returns ``valid=False`` with ``errors`` and ``warnings``;
    /// request failures raise ``PerceptionError`` instead.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[ValidationResult]",
        imports = ("collections.abc",)
    ))]
    fn validate<'py>(
        &self,
        py: Python<'py>,
        workflow: &PyPerceptionWorkflow,
    ) -> PyResult<Bound<'py, PyAny>> {
        let service = Arc::clone(&self.0);
        let workflow = workflow.0.clone();
        tokio_runtime::future_into_py(py, async move {
            let result = service
                .lock()
                .await
                .validate(&workflow)
                .await
                .map_err(perception_error)?;
            Python::attach(|py| Py::new(py, PyValidationResult::from(result)))
        })
    }

    /// Deploy a workflow and return its session handle.
    ///
    /// Retrying a deployment can create another session.
    /// Rejection raises ``DeploymentValidationError`` with ``issues``; other failures
    /// raise ``PerceptionDeploymentError``. Await ``session.stop()`` when finished.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[PerceptionSession]",
        imports = ("collections.abc",)
    ))]
    fn deploy<'py>(
        &self,
        py: Python<'py>,
        workflow: &PyPerceptionWorkflow,
    ) -> PyResult<Bound<'py, PyAny>> {
        let service = Arc::clone(&self.0);
        let workflow = workflow.0.clone();
        tokio_runtime::future_into_py(py, async move {
            let session = match service.lock().await.deploy(&workflow).await {
                Ok(session) => session,
                Err(error) => return Err(deployment_error(error)?),
            };
            Python::attach(|py| Py::new(py, PyPerceptionSession(session)))
        })
    }

    /// Return handles for the sessions reported by the service.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[list[PerceptionSession]]",
        imports = ("collections.abc",)
    ))]
    fn list_sessions<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let service = Arc::clone(&self.0);
        tokio_runtime::future_into_py(py, async move {
            let sessions = service
                .lock()
                .await
                .list_sessions()
                .await
                .map_err(perception_error)?;
            Python::attach(|py| {
                PyList::new(py, sessions.into_iter().map(PyPerceptionSession))
                    .map(|sessions| sessions.unbind())
            })
        })
    }
}

fn validation_severity_name(severity: ValidationSeverity) -> String {
    match severity {
        ValidationSeverity::Unspecified => "unspecified".to_string(),
        ValidationSeverity::Error => "error".to_string(),
        ValidationSeverity::Warning => "warning".to_string(),
        ValidationSeverity::Unknown(value) => format!("unknown:{value}"),
    }
}

fn resolved_stage_role_name(role: ResolvedStageRole) -> String {
    match role {
        ResolvedStageRole::Unspecified => "unspecified".to_string(),
        ResolvedStageRole::Source => "source".to_string(),
        ResolvedStageRole::Processing => "processing".to_string(),
        ResolvedStageRole::Output => "output".to_string(),
        ResolvedStageRole::Unknown(value) => format!("unknown:{value}"),
    }
}

fn perception_error(error: RustPerceptionServiceError) -> pyo3::PyErr {
    PerceptionError::new_err(error.to_string())
}

fn deployment_error(error: RustPerceptionServiceError) -> PyResult<PyErr> {
    match error {
        RustPerceptionServiceError::Workflow(issues) => Python::attach(|py| {
            let issues = PyList::new(py, issues.into_iter().map(PyValidationIssue::from))?;
            let error = DeploymentValidationError::new_err("perception workflow validation failed");
            error.value(py).setattr("issues", &issues)?;
            Ok(error)
        }),
        other => Ok(PerceptionDeploymentError::new_err(other.to_string())),
    }
}

pub(crate) fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let module = PyModule::new(parent.py(), "cairn.perception")?;
    module.add("PerceptionError", parent.py().get_type::<PerceptionError>())?;
    let deployment_validation_error = parent.py().get_type::<DeploymentValidationError>();
    deployment_validation_error.setattr("issues", parent.py().None())?;
    module.add("DeploymentValidationError", deployment_validation_error)?;
    module.add(
        "PerceptionDeploymentError",
        parent.py().get_type::<PerceptionDeploymentError>(),
    )?;

    module.add_class::<PyDebugOutput>()?;
    module.add_class::<PyStageHandle>()?;
    module.add_class::<PyServiceInfo>()?;
    module.add_class::<PyValidationIssue>()?;
    module.add_class::<PyResolvedStage>()?;
    module.add_class::<PyValidationResult>()?;
    module.add_class::<PyDebugPorts>()?;
    module.add_class::<PySessionTopics>()?;
    module.add_class::<PyStatusInfo>()?;
    module.add_class::<PySessionState>()?;
    module.add_class::<PySessionStatus>()?;
    module.add_class::<PySessionSnapshot>()?;
    module.add_class::<PyPerceptionSession>()?;
    module.add_class::<PyPerceptionWorkflow>()?;
    module.add_class::<PyPerceptionService>()?;
    crate::perception_result::register(&module)?;
    parent.add_submodule(&module)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("cairn.perception", module)?;
    Ok(())
}

pyo3_stub_gen::module_doc!(
    "cairn.perception",
    "Python interface for constructing, validating, and deploying Perception workflows."
);
