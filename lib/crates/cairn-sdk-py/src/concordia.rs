use crate::util::build_runtime;
use cairn_sdk::concordia_service::{
    AudioOutput, ConcordiaError as RustConcordiaError, ConcordiaService as RustConcordiaService,
    RunBrickOptions, RunBrickOutput,
};
use numpy::PyArray1;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::types::{PyAny, PyAnyMethods, PyDict, PyDictMethods, PyModule, PyModuleMethods};
use pyo3::{Bound, Py, PyErr, PyResult, Python, pyclass, pymethods};
use pyo3_stub_gen::create_exception;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use tokio::runtime::Runtime;

create_exception!(
    cairn_sdk,
    ConcordiaError,
    PyException,
    "Raised when a Concordia request fails."
);

enum BindingError {
    Concordia(RustConcordiaError),
    InvalidArguments { message: String },
}

impl From<RustConcordiaError> for BindingError {
    fn from(error: RustConcordiaError) -> Self {
        Self::Concordia(error)
    }
}

/// Entry point for running Concordia bricks and collecting their outputs.
///
/// Create `ConcordiaService(endpoint)` with the service address, then call
/// `run_brick()` with the brick you want to execute and its input payload.
#[gen_stub_pyclass]
#[pyclass(unsendable, module = "cairn_sdk", name = "ConcordiaService")]
pub(crate) struct PyConcordiaService {
    tokio_runtime: Runtime,
    inner_service: RustConcordiaService,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyConcordiaService {
    /// Create a Concordia service client.
    ///
    /// Parameters
    /// ----------
    /// endpoint:
    ///     Service address to connect to, for example `http://127.0.0.1:50052`.
    ///
    /// Returns
    /// -------
    /// ConcordiaService
    ///     A service handle that can run bricks and return typed outputs.
    #[new]
    #[pyo3(text_signature = "(endpoint)")]
    #[gen_stub(override_return_type(type_repr = "'ConcordiaService'"))]
    fn new(endpoint: String) -> PyResult<Self> {
        let tokio_runtime = build_runtime().map_err(|error| {
            ConcordiaError::new_err(format!("failed to initialize concordia runtime: {error}"))
        })?;
        let inner_service = tokio_runtime
            .block_on(RustConcordiaService::new(&endpoint))
            .map_err(binding_error_to_pyerr)?;

        Ok(Self {
            tokio_runtime,
            inner_service,
        })
    }

    /// Run a Concordia brick and return its output.
    ///
    /// Parameters
    /// ----------
    /// brick_type:
    ///     The kind of brick to run, such as `tts` or `object-detection`.
    /// brick_variant:
    ///     The specific variant to execute within that brick type.
    /// options:
    ///     Input payload for the brick. Provide exactly one of `{"text": "..."}`
    ///     or `{"image_bytes": b"..."}`.
    ///
    /// Returns
    /// -------
    /// AudioOutput | ObjectDetectionOutput
    ///     The typed output returned by the brick that was run.
    #[pyo3(signature = (brick_type, brick_variant, options))]
    #[pyo3(text_signature = "($self, brick_type, brick_variant, options)")]
    #[gen_stub(override_return_type(type_repr = "AudioOutput | ObjectDetectionOutput"))]
    fn run_brick<'py>(
        &mut self,
        py: Python<'py>,
        brick_type: String,
        brick_variant: String,
        #[gen_stub(override_type(type_repr = "dict[builtins.str, builtins.str | builtins.bytes]", imports=("builtins")))]
        options: &Bound<'_, PyDict>,
    ) -> PyResult<Py<PyAny>> {
        let options = build_run_brick_options(options).map_err(binding_error_to_pyerr)?;
        let output = self
            .tokio_runtime
            .block_on(
                self.inner_service
                    .run_brick(&brick_type, &brick_variant, options),
            )
            .map_err(binding_error_to_pyerr)?;
        into_python_output(py, output)
    }
}

/// Audio samples returned by a Concordia brick.
///
/// Attributes
/// ----------
/// left_channel:
///     Left audio channel as a one-dimensional NumPy array of `float32`.
/// right_channel:
///     Right audio channel as a one-dimensional NumPy array of `float32`.
#[gen_stub_pyclass]
#[pyclass(module = "cairn_sdk", frozen, name = "AudioOutput")]
pub(crate) struct PyAudioOutput {
    left_channel: Py<PyArray1<f32>>,
    right_channel: Py<PyArray1<f32>>,
}

impl PyAudioOutput {
    fn new(py: Python<'_>, output: AudioOutput) -> Self {
        Self {
            left_channel: PyArray1::from_vec(py, output.left_channel).unbind(),
            right_channel: PyArray1::from_vec(py, output.right_channel).unbind(),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl PyAudioOutput {
    /// Left audio channel as a one-dimensional NumPy array of `float32`.
    #[getter]
    #[gen_stub(override_return_type(type_repr = "numpy.typing.NDArray[numpy.float32]", imports=("numpy", "numpy.typing")))]
    fn left_channel(&self, py: Python<'_>) -> Py<PyArray1<f32>> {
        self.left_channel.clone_ref(py)
    }

    /// Right audio channel as a one-dimensional NumPy array of `float32`.
    #[getter]
    #[gen_stub(override_return_type(type_repr = "numpy.typing.NDArray[numpy.float32]", imports=("numpy", "numpy.typing")))]
    fn right_channel(&self, py: Python<'_>) -> Py<PyArray1<f32>> {
        self.right_channel.clone_ref(py)
    }
}

/// One detected object returned by an object-detection brick.
///
/// Attributes
/// ----------
/// box:
///     Bounding box coordinates as a one-dimensional NumPy array of `float32`.
/// class_id:
///     Numeric class identifier assigned by the model.
/// score:
///     Confidence score for the detection.
/// class_name:
///     Human-readable class label for the detection.
#[gen_stub_pyclass]
#[pyclass(module = "cairn_sdk", frozen, name = "Detection")]
pub(crate) struct PyDetection {
    box_values: Py<PyArray1<f32>>,
    #[pyo3(get)]
    class_id: i32,
    #[pyo3(get)]
    score: f32,
    #[pyo3(get)]
    class_name: String,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyDetection {
    /// Bounding box coordinates as a one-dimensional NumPy array of `float32`.
    #[getter]
    #[gen_stub(override_return_type(type_repr = "numpy.typing.NDArray[numpy.float32]", imports=("numpy", "numpy.typing")))]
    fn get_box(&self, py: Python<'_>) -> Py<PyArray1<f32>> {
        self.box_values.clone_ref(py)
    }
}

/// Collection of detections returned by an object-detection brick.
///
/// Attributes
/// ----------
/// detections:
///     Detected objects returned by the brick.
#[gen_stub_pyclass]
#[pyclass(module = "cairn_sdk", frozen, name = "ObjectDetectionOutput")]
pub(crate) struct PyObjectDetectionOutput {
    detections: Vec<Py<PyDetection>>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyObjectDetectionOutput {
    /// Detected objects returned by the brick.
    #[getter]
    fn detections(&self, py: Python<'_>) -> Vec<Py<PyDetection>> {
        self.detections
            .iter()
            .map(|detection| detection.clone_ref(py))
            .collect()
    }
}

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("ConcordiaError", module.py().get_type::<ConcordiaError>())?;
    module.add_class::<PyAudioOutput>()?;
    module.add_class::<PyConcordiaService>()?;
    module.add_class::<PyDetection>()?;
    module.add_class::<PyObjectDetectionOutput>()?;
    Ok(())
}

fn build_run_brick_options(options: &Bound<'_, PyDict>) -> Result<RunBrickOptions, BindingError> {
    let text = options
        .get_item("text")
        .map_err(|error| dict_option_error("text", "read", error))?
        .map(|value| value.extract::<Option<String>>())
        .transpose()
        .map_err(|error| dict_option_error("text", "be a string", error))?
        .flatten();
    let image_bytes = options
        .get_item("image_bytes")
        .map_err(|error| dict_option_error("image_bytes", "read", error))?
        .map(|value| value.extract::<Option<Vec<u8>>>())
        .transpose()
        .map_err(|error| dict_option_error("image_bytes", "be bytes", error))?
        .flatten();

    validate_run_brick_options(&text, &image_bytes)?;

    match (text, image_bytes) {
        (Some(text), None) => Ok(RunBrickOptions::Text { text }),
        (None, Some(image_bytes)) => Ok(RunBrickOptions::Image { image_bytes }),
        _ => unreachable!("validated run_brick options must contain exactly one payload"),
    }
}

fn dict_option_error(key: &str, expectation: &str, error: PyErr) -> BindingError {
    BindingError::InvalidArguments {
        message: format!("run_brick option '{key}' must {expectation}: {error}"),
    }
}

fn validate_run_brick_options(
    text: &Option<String>,
    image_bytes: &Option<Vec<u8>>,
) -> Result<(), BindingError> {
    match (text, image_bytes) {
        (Some(_), None) | (None, Some(_)) => Ok(()),
        (None, None) => Err(BindingError::InvalidArguments {
            message: "exactly one of 'text' or 'image_bytes' must be provided".to_string(),
        }),
        (Some(_), Some(_)) => Err(BindingError::InvalidArguments {
            message: "only one of 'text' or 'image_bytes' can be provided".to_string(),
        }),
    }
}

fn binding_error_to_pyerr(error: impl Into<BindingError>) -> PyErr {
    match error.into() {
        BindingError::Concordia(error) => ConcordiaError::new_err(error.to_string()),
        BindingError::InvalidArguments { message } => PyValueError::new_err(message),
    }
}

fn into_python_output(py: Python<'_>, output: RunBrickOutput) -> PyResult<Py<PyAny>> {
    match output {
        RunBrickOutput::Audio(audio) => {
            Py::new(py, PyAudioOutput::new(py, audio)).map(|value| value.into_any())
        }
        RunBrickOutput::Detections(output) => {
            let detections = output
                .detections
                .into_iter()
                .map(|detection| {
                    Py::new(
                        py,
                        PyDetection {
                            box_values: PyArray1::from_vec(py, detection.r#box).unbind(),
                            class_id: detection.class_id,
                            score: detection.score,
                            class_name: detection.class_name,
                        },
                    )
                })
                .collect::<PyResult<Vec<_>>>()?;
            Py::new(py, PyObjectDetectionOutput { detections }).map(|value| value.into_any())
        }
    }
}
