// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::sync::Arc;

use cairn::notification_service::{Notification, NotificationService, NotificationSubscription};
use pyo3::exceptions::{PyRuntimeError, PyTypeError};
use pyo3::types::{PyAnyMethods, PyBytes, PyModule, PyModuleMethods};
use pyo3::{Bound, Py, PyAny, PyRef, PyResult, Python, pyclass, pymethods};
use pyo3_async_runtimes::{TaskLocals, tokio as tokio_runtime};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use tokio::sync::Mutex;

/// Client for subscribing to notifications from the Cairn messaging service.
#[gen_stub_pyclass(module = "cairn.notification")]
#[pyclass(module = "cairn", name = "NotificationService")]
pub struct PyNotificationService {
    inner: Arc<Mutex<NotificationService>>,
}

/// A notification received from the messaging service.
#[gen_stub_pyclass(module = "cairn.notification")]
#[pyclass(frozen, module = "cairn", name = "Notification")]
pub struct PyNotification {
    channel: String,
    payload: Py<PyBytes>,
}

impl PyNotification {
    fn from_notification(py: Python<'_>, notification: Notification) -> Self {
        Self {
            channel: notification.channel,
            payload: PyBytes::new(py, notification.payload.as_ref()).unbind(),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl PyNotification {
    /// Channel on which this notification was received.
    #[getter]
    fn channel(&self) -> String {
        self.channel.clone()
    }

    /// Raw notification payload.
    #[getter]
    #[gen_stub(override_return_type(type_repr = "builtins.bytes", imports = ("builtins",)))]
    fn payload(&self, py: Python<'_>) -> Py<PyBytes> {
        self.payload.clone_ref(py)
    }
}

/// An identifier for a subscription registered with the notification service.
#[gen_stub_pyclass(module = "cairn.notification")]
#[pyclass(frozen, module = "cairn", name = "NotificationSubscription")]
pub struct PyNotificationSubscription {
    subscription_id: NotificationSubscription,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyNotificationService {
    /// Create a notification service client.
    #[new]
    #[pyo3(signature = (endpoint=None))]
    #[pyo3(text_signature = "(endpoint=None)")]
    #[gen_stub(override_return_type(type_repr = "'NotificationService'"))]
    fn new(py: Python<'_>, endpoint: Option<String>) -> PyResult<Self> {
        let inner = py
            .detach(|| tokio_runtime::get_runtime().block_on(NotificationService::new(endpoint)))
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;

        Ok(Self {
            inner: Arc::new(Mutex::new(inner)),
        })
    }

    /// Enter an asynchronous context for this notification service.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[NotificationService]",
        imports = ("collections.abc",)
    ))]
    fn __aenter__<'py>(slf: PyRef<'_, Self>, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let service: Py<PyNotificationService> = slf.into();

        tokio_runtime::future_into_py(py, async move {
            Ok(Python::attach(|py| {
                service.into_bound(py).into_any().unbind()
            }))
        })
    }

    /// Subscribe a Python callback to a channel of the messaging service.
    ///
    /// The callback should be a callable receiving a `Notification` and must return an awaitable.
    /// Callback exceptions are reported as unraisable Python exceptions.
    ///
    /// This operation is not cancellation-safe. Canceling it while awaiting acknowledgment
    /// can leave local and subscription state inconsistent.
    #[pyo3(signature = (channel, handler))]
    #[pyo3(text_signature = "($self, channel, handler)")]
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[NotificationSubscription]",
        imports = ("collections.abc",)
    ))]
    fn subscribe<'py>(
        &self,
        py: Python<'py>,
        channel: String,
        #[gen_stub(override_type(
            type_repr = "collections.abc.Callable[[Notification], collections.abc.Awaitable[None]]",
            imports = ("collections.abc",)
        ))]
        handler: Py<PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        if !handler.bind(py).is_callable() {
            return Err(PyTypeError::new_err(
                "notification handler must be callable",
            ));
        }

        let locals = tokio_runtime::get_current_locals(py)?;
        let service = Arc::clone(&self.inner);
        let callback_locals = locals.clone();

        tokio_runtime::future_into_py_with_locals(py, locals, async move {
            let mut service = service.lock().await;
            let subscription_id = service
                .subscribe(&channel, move |notification| {
                    let handler = Python::attach(|py| handler.clone_ref(py));
                    let locals = callback_locals.clone();
                    async move { invoke_handler(handler, locals, notification).await }
                })
                .await
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
            Python::attach(|py| Py::new(py, PyNotificationSubscription { subscription_id }))
        })
    }

    /// Remove a notification subscription using its identifier.
    ///
    /// This operation is not cancellation-safe. Canceling it while awaiting acknowledgment
    /// can leave local and subscription state inconsistent.
    #[pyo3(signature = (subscription))]
    #[pyo3(text_signature = "($self, subscription)")]
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[None]",
        imports = ("collections.abc",)
    ))]
    fn unsubscribe<'py>(
        &self,
        py: Python<'py>,
        subscription: PyRef<'_, PyNotificationSubscription>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let subscription_id = subscription.subscription_id;
        let service = Arc::clone(&self.inner);

        tokio_runtime::future_into_py(py, async move {
            service
                .lock()
                .await
                .unsubscribe(subscription_id)
                .await
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
            Ok(())
        })
    }

    /// Close the notification service. This will also terminate all the channel subscriptions.
    #[pyo3(text_signature = "($self)")]
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[None]",
        imports = ("collections.abc",)
    ))]
    fn close<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let service = Arc::clone(&self.inner);

        tokio_runtime::future_into_py(py, async move {
            service
                .lock()
                .await
                .close()
                .await
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
            Ok(())
        })
    }

    /// Exit an asynchronous context and close the notification service.
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[None]",
        imports = ("collections.abc",)
    ))]
    fn __aexit__<'py>(
        &self,
        py: Python<'py>,
        _exception_type: Py<PyAny>,
        _exception: Py<PyAny>,
        _traceback: Py<PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        self.close(py)
    }
}

pub(crate) fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let module = PyModule::new(parent.py(), "cairn.notification")?;
    module.add_class::<PyNotificationService>()?;
    module.add_class::<PyNotification>()?;
    module.add_class::<PyNotificationSubscription>()?;
    parent.add_submodule(&module)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("cairn.notification", module)?;
    Ok(())
}

pyo3_stub_gen::module_doc!(
    "cairn.notification",
    "Python interface for subscribing to notifications from the Cairn messaging service."
);

async fn invoke_handler(handler: Py<PyAny>, locals: TaskLocals, notification: Notification) {
    let future = Python::attach(|py| {
        let notification = Py::new(py, PyNotification::from_notification(py, notification))?;
        let result = handler.call1(py, (notification,))?;
        let is_awaitable = py
            .import("inspect")?
            .call_method1("isawaitable", (&result,))?
            .extract::<bool>()?;
        if !is_awaitable {
            return Err(PyTypeError::new_err(
                "notification handler must return an awaitable",
            ));
        }
        pyo3_async_runtimes::into_future_with_locals(&locals, result.bind(py).clone())
    });

    let result = match future {
        Ok(future) => future.await,
        Err(error) => Err(error),
    };

    if let Err(error) = result {
        Python::attach(|py| error.write_unraisable(py, Some(handler.bind(py))));
    }
}
