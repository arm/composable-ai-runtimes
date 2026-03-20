use crate::util::build_runtime;
use cairn_sdk::concordia_service::{
    AudioOutput, ConcordiaError as RustConcordiaError, ConcordiaService as RustConcordiaService,
    RunBrickOptions, RunBrickOutput,
};
use numpy::PyArray1;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::types::{PyAny, PyAnyMethods, PyDict, PyDictMethods, PyModule, PyModuleMethods};
use pyo3::{Bound, Py, PyErr, PyResult, Python, pyclass, pymethods};
use tokio::runtime::Runtime;

create_exception!(cairn_sdk, PyConcordiaError, PyException);

enum BindingError {
    Concordia(RustConcordiaError),
    InvalidArguments { message: String },
}

impl From<RustConcordiaError> for BindingError {
    fn from(error: RustConcordiaError) -> Self {
        Self::Concordia(error)
    }
}

#[pyclass(unsendable, module = "cairn_sdk", name = "ConcordiaService")]
pub(crate) struct PyConcordiaService {
    tokio_runtime: Runtime,
    inner_service: RustConcordiaService,
}

#[pymethods]
impl PyConcordiaService {
    #[new]
    fn new(endpoint: String) -> PyResult<Self> {
        let tokio_runtime = build_runtime().map_err(|error| {
            PyConcordiaError::new_err(format!("failed to initialize concordia runtime: {error}"))
        })?;
        let inner_service = tokio_runtime
            .block_on(RustConcordiaService::new(&endpoint))
            .map_err(binding_error_to_pyerr)?;

        Ok(Self {
            tokio_runtime,
            inner_service,
        })
    }

    #[pyo3(signature = (brick_type, brick_variant, options))]
    fn run_brick<'py>(
        &mut self,
        py: Python<'py>,
        brick_type: String,
        brick_variant: String,
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

#[pyclass(module = "cairn_sdk", frozen, name = "AudioOutput")]
pub(crate) struct PyAudioOutput {
    #[pyo3(get)]
    left_channel: Py<PyArray1<f32>>,
    #[pyo3(get)]
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

#[pyclass(module = "cairn_sdk", frozen, name = "Detection")]
pub(crate) struct PyDetection {
    #[pyo3(get, name = "box")]
    box_values: Py<PyArray1<f32>>,
    #[pyo3(get)]
    class_id: i32,
    #[pyo3(get)]
    score: f32,
    #[pyo3(get)]
    class_name: String,
}

#[pyclass(module = "cairn_sdk", frozen, name = "ObjectDetectionOutput")]
pub(crate) struct PyObjectDetectionOutput {
    #[pyo3(get)]
    detections: Vec<Py<PyDetection>>,
}

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("ConcordiaError", module.py().get_type::<PyConcordiaError>())?;
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
        BindingError::Concordia(error) => PyConcordiaError::new_err(error.to_string()),
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
