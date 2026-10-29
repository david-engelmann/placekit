//! PyO3 bindings for `placekit-core`.
//!
//! This module is deliberately thin. All protocol logic lives in the
//! `placekit-core` crate; this layer only converts arguments (request bodies
//! arrive as dicts and are deserialized into the core's typed request
//! structs, so validation stays in Rust), runs the core's async futures on a
//! shared Tokio runtime for both the sync and async Python APIs, and
//! translates core errors into the `PlacesError` exception defined here.
//! The Python package re-exports a friendlier exception hierarchy built on
//! top of the `kind` attribute this layer sets.

use std::sync::Arc;

use placekit_core::models::{AutocompleteRequest, NearbySearchRequest, TextSearchRequest};
use placekit_core::{Client as CoreClient, Error as CoreError, FieldMask};
use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyTuple};
use serde_json::Value;

create_exception!(
    _placekit,
    PlacesError,
    pyo3::exceptions::PyException,
    "Base exception raised by the Rust core. Carries `kind`, `status_code` and `google_status` attributes."
);

/// Translate a core error into a `PlacesError` with structured attributes
/// the Python layer uses to pick a concrete exception subclass. API errors
/// also carry the envelope `error_code`, the parsed `details`, and any
/// field or quota violations extracted from them (C6).
fn to_pyerr(py: Python<'_>, err: CoreError) -> PyErr {
    let pyerr = PyErr::new::<PlacesError, _>(err.to_string());
    let instance = pyerr.value(py);
    let _ = instance.setattr("kind", err.kind());
    let _ = instance.setattr("status_code", err.status_code());
    let _ = instance.setattr("google_status", err.google_status());
    let _ = instance.setattr("error_code", err.error_code());
    let _ = instance.setattr("status_mismatch", err.status_mismatch());
    let _ = instance.setattr("retryable", err.retryable());
    let _ = instance.setattr("retry_after", err.retry_after());
    if let Ok(details) = serde_json::to_value(err.details()) {
        if let Ok(value) = value_to_py(py, &details) {
            let _ = instance.setattr("details", value);
        }
    }
    let violations: Vec<(String, String)> = err.field_violations();
    if let Ok(value) = value_to_py(
        py,
        &serde_json::Value::Array(
            violations
                .iter()
                .map(|(field, description)| {
                    serde_json::json!({"field": field, "description": description})
                })
                .collect(),
        ),
    ) {
        let _ = instance.setattr("field_violations", value);
    }
    if let Ok(value) = value_to_py(py, &serde_json::Value::Array(err.quota_violations())) {
        let _ = instance.setattr("quota_violations", value);
    }
    pyerr
}

fn mask_from(py: Python<'_>, fields: Option<Vec<String>>) -> PyResult<Option<FieldMask>> {
    match fields {
        None => Ok(None),
        Some(paths) => FieldMask::new(paths).map(Some).map_err(|e| to_pyerr(py, e)),
    }
}

fn body_to_request<T>(body: &Bound<'_, PyDict>) -> PyResult<T>
where
    T: serde::de::DeserializeOwned,
{
    // A body that does not fit the typed request shape is a local call
    // error (for example a circle in a Text Search location restriction,
    // which is rectangle only), so it raises the config error like the
    // core's own local validations instead of escaping as a bare
    // PyValueError outside the exception hierarchy.
    pythonize::depythonize(body.as_any()).map_err(|e| {
        to_pyerr(
            body.py(),
            CoreError::Config {
                detail: e.to_string(),
            },
        )
    })
}

fn value_to_py(py: Python<'_>, value: &Value) -> PyResult<PyObject> {
    // A value that cannot be converted for Python is a decode failure
    // of this layer, reported inside the exception hierarchy like the
    // core's own decode errors rather than as a bare PyValueError.
    pythonize::pythonize(py, value)
        .map(|bound| bound.unbind())
        .map_err(|e| {
            to_pyerr(
                py,
                CoreError::Decode {
                    detail: e.to_string(),
                    status: None,
                },
            )
        })
}

fn result_to_py<T>(py: Python<'_>, result: Result<T, CoreError>) -> PyResult<PyObject>
where
    T: serde::Serialize,
{
    match result {
        Ok(value) => {
            let json = serde_json::to_value(&value).map_err(|e| {
                to_pyerr(
                    py,
                    CoreError::Decode {
                        detail: e.to_string(),
                        status: None,
                    },
                )
            })?;
            value_to_py(py, &json)
        }
        Err(e) => Err(to_pyerr(py, e)),
    }
}

/// Photo results cross the boundary as a tagged 3-tuple so the Python
/// layer can tell the two wire forms apart: `("bytes", content, content
/// type)` for the downloaded image, `("uri", photo_uri, name)` when the
/// redirect was skipped and the endpoint answered with JSON.
fn photo_to_py(
    py: Python<'_>,
    result: Result<placekit_core::models::PhotoMedia, CoreError>,
) -> PyResult<PyObject> {
    match result {
        Ok(placekit_core::models::PhotoMedia::Bytes(photo)) => {
            let tag = "bytes"
                .into_pyobject(py)
                .map_err(|e| PyValueError::new_err(e.to_string()))?
                .unbind()
                .into_any();
            let bytes = PyBytes::new(py, &photo.bytes).unbind().into_any();
            let content_type = photo
                .content_type
                .into_pyobject(py)
                .map_err(|e| PyValueError::new_err(e.to_string()))?
                .unbind()
                .into_any();
            let tuple = PyTuple::new(py, [tag, bytes, content_type])
                .map_err(|e| PyValueError::new_err(e.to_string()))?;
            Ok(tuple.unbind().into_any())
        }
        Ok(placekit_core::models::PhotoMedia::Uri(media)) => {
            let tag = "uri"
                .into_pyobject(py)
                .map_err(|e| PyValueError::new_err(e.to_string()))?
                .unbind()
                .into_any();
            let uri = media
                .photo_uri
                .into_pyobject(py)
                .map_err(|e| PyValueError::new_err(e.to_string()))?
                .unbind()
                .into_any();
            let name = media
                .name
                .into_pyobject(py)
                .map_err(|e| PyValueError::new_err(e.to_string()))?
                .unbind()
                .into_any();
            let tuple = PyTuple::new(py, [tag, uri, name])
                .map_err(|e| PyValueError::new_err(e.to_string()))?;
            Ok(tuple.unbind().into_any())
        }
        Err(e) => Err(to_pyerr(py, e)),
    }
}

/// The Rust client handle wrapped for Python.
#[pyclass(name = "Client")]
struct PyClient {
    inner: Arc<CoreClient>,
}

#[pymethods]
impl PyClient {
    #[new]
    #[pyo3(signature = (api_key, base_url=None, timeout=None))]
    fn new(
        py: Python<'_>,
        api_key: String,
        base_url: Option<String>,
        timeout: Option<f64>,
    ) -> PyResult<Self> {
        let mut builder = CoreClient::builder(api_key);
        if let Some(base_url) = base_url {
            builder = builder.base_url(base_url);
        }
        if let Some(timeout) = timeout {
            if !timeout.is_finite() || timeout <= 0.0 {
                return Err(PyValueError::new_err(
                    "timeout must be a positive, finite number of seconds",
                ));
            }
            builder = builder.timeout(std::time::Duration::from_secs_f64(timeout));
        }
        let client = builder.build().map_err(|e| match e.kind() {
            "config" => PyValueError::new_err(e.to_string()),
            _ => to_pyerr(py, e),
        })?;
        Ok(Self {
            inner: Arc::new(client),
        })
    }

    // -- Text Search -------------------------------------------------------

    #[pyo3(signature = (body, fields=None))]
    fn text_search(
        &self,
        py: Python<'_>,
        body: Bound<'_, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<PyObject> {
        let request: TextSearchRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.inner.clone();
        let result = py.allow_threads(|| {
            pyo3_async_runtimes::tokio::get_runtime()
                .block_on(async move { inner.text_search(&request, mask.as_ref()).await })
        });
        result_to_py(py, result)
    }

    #[pyo3(signature = (body, fields=None))]
    fn text_search_async<'py>(
        &self,
        py: Python<'py>,
        body: Bound<'py, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request: TextSearchRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let result = inner.text_search(&request, mask.as_ref()).await;
            Python::with_gil(|py| result_to_py(py, result))
        })
    }

    // -- Nearby Search -----------------------------------------------------

    #[pyo3(signature = (body, fields=None))]
    fn nearby_search(
        &self,
        py: Python<'_>,
        body: Bound<'_, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<PyObject> {
        let request: NearbySearchRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.inner.clone();
        let result = py.allow_threads(|| {
            pyo3_async_runtimes::tokio::get_runtime()
                .block_on(async move { inner.nearby_search(&request, mask.as_ref()).await })
        });
        result_to_py(py, result)
    }

    #[pyo3(signature = (body, fields=None))]
    fn nearby_search_async<'py>(
        &self,
        py: Python<'py>,
        body: Bound<'py, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request: NearbySearchRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let result = inner.nearby_search(&request, mask.as_ref()).await;
            Python::with_gil(|py| result_to_py(py, result))
        })
    }

    // -- Place Details -----------------------------------------------------

    #[pyo3(signature = (place_id, fields=None, language_code=None, region_code=None, session_token=None))]
    fn place_details(
        &self,
        py: Python<'_>,
        place_id: String,
        fields: Option<Vec<String>>,
        language_code: Option<String>,
        region_code: Option<String>,
        session_token: Option<String>,
    ) -> PyResult<PyObject> {
        let mask = mask_from(py, fields)?;
        let inner = self.inner.clone();
        let result = py.allow_threads(|| {
            pyo3_async_runtimes::tokio::get_runtime().block_on(async move {
                inner
                    .place_details(
                        &place_id,
                        mask.as_ref(),
                        language_code.as_deref(),
                        region_code.as_deref(),
                        session_token.as_deref(),
                    )
                    .await
            })
        });
        result_to_py(py, result)
    }

    #[pyo3(signature = (place_id, fields=None, language_code=None, region_code=None, session_token=None))]
    fn place_details_async<'py>(
        &self,
        py: Python<'py>,
        place_id: String,
        fields: Option<Vec<String>>,
        language_code: Option<String>,
        region_code: Option<String>,
        session_token: Option<String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let mask = mask_from(py, fields)?;
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let result = inner
                .place_details(
                    &place_id,
                    mask.as_ref(),
                    language_code.as_deref(),
                    region_code.as_deref(),
                    session_token.as_deref(),
                )
                .await;
            Python::with_gil(|py| result_to_py(py, result))
        })
    }

    // -- Autocomplete ------------------------------------------------------

    #[pyo3(signature = (body, fields=None))]
    fn autocomplete(
        &self,
        py: Python<'_>,
        body: Bound<'_, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<PyObject> {
        let request: AutocompleteRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.inner.clone();
        let result = py.allow_threads(|| {
            pyo3_async_runtimes::tokio::get_runtime()
                .block_on(async move { inner.autocomplete(&request, mask.as_ref()).await })
        });
        result_to_py(py, result)
    }

    #[pyo3(signature = (body, fields=None))]
    fn autocomplete_async<'py>(
        &self,
        py: Python<'py>,
        body: Bound<'py, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request: AutocompleteRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let result = inner.autocomplete(&request, mask.as_ref()).await;
            Python::with_gil(|py| result_to_py(py, result))
        })
    }

    // -- Place Photos ------------------------------------------------------

    #[pyo3(signature = (photo_name, max_width_px=None, max_height_px=None, skip_http_redirect=false))]
    fn place_photo(
        &self,
        py: Python<'_>,
        photo_name: String,
        max_width_px: Option<u32>,
        max_height_px: Option<u32>,
        skip_http_redirect: bool,
    ) -> PyResult<PyObject> {
        let inner = self.inner.clone();
        let result = py.allow_threads(|| {
            pyo3_async_runtimes::tokio::get_runtime().block_on(async move {
                inner
                    .place_photo(&photo_name, max_width_px, max_height_px, skip_http_redirect)
                    .await
            })
        });
        photo_to_py(py, result)
    }

    #[pyo3(signature = (photo_name, max_width_px=None, max_height_px=None, skip_http_redirect=false))]
    fn place_photo_async<'py>(
        &self,
        py: Python<'py>,
        photo_name: String,
        max_width_px: Option<u32>,
        max_height_px: Option<u32>,
        skip_http_redirect: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let result = inner
                .place_photo(&photo_name, max_width_px, max_height_px, skip_http_redirect)
                .await;
            Python::with_gil(|py| photo_to_py(py, result))
        })
    }
}

#[pymodule]
fn _placekit(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyClient>()?;
    m.add("PlacesError", m.py().get_type::<PlacesError>())?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
