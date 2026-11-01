//! PyO3 bindings for `placekit-core`.
//!
//! This module is deliberately thin. All protocol logic lives in the
//! `placekit-core` crate; this layer only converts arguments (request bodies
//! arrive as dicts and are deserialized into the core's typed request
//! structs, so validation stays in Rust), runs the core's async futures on a
//! Tokio runtime owned by this layer for both the sync and async Python
//! APIs, and translates core errors into the `PlacesError` exception defined
//! here. The Python package re-exports a friendlier exception hierarchy
//! built on top of the `kind` attribute this layer sets.
//!
//! The runtime is process wide but fork aware. `pyo3-async-runtimes`
//! keeps its own runtime in a process global that is built once and
//! can never be replaced, and a runtime built before a fork is dead
//! in the child because its worker threads do not survive the fork.
//! These bindings therefore keep their own runtime, keyed by the
//! process id it was built under, and spawn through the generic
//! `pyo3-async-runtimes` bridge onto that runtime. The first call a
//! forked child makes builds a fresh runtime for its own process id,
//! and the dead parent runtime is leaked rather than dropped, so no
//! shutdown machinery ever runs against threads that no longer exist.

use std::future::Future;
use std::pin::Pin;
use std::sync::{Arc, Mutex};

use placekit_core::models::{AutocompleteRequest, NearbySearchRequest, TextSearchRequest};
use placekit_core::{Client as CoreClient, Error as CoreError, FieldMask};
use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyDict, PyList, PyTuple};
use serde_json::Value;

create_exception!(
    _placekit,
    PlacesError,
    pyo3::exceptions::PyException,
    "Base exception raised by the Rust core. Carries `kind`, `status_code` and `google_status` attributes."
);

/// The process wide Tokio runtime, paired with the process id it was
/// built under. One runtime serves every client in a process for the
/// life of that process. A forked child inherits the slot but not the
/// worker threads, so the first access under a new process id builds
/// a replacement and leaks the dead runtime instead of dropping it.
static PROCESS_RUNTIME: Mutex<Option<(u32, Arc<tokio::runtime::Runtime>)>> = Mutex::new(None);

fn shared_runtime() -> Arc<tokio::runtime::Runtime> {
    let pid = std::process::id();
    let mut slot = PROCESS_RUNTIME
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    if let Some((built_pid, runtime)) = slot.as_ref() {
        if *built_pid == pid {
            return Arc::clone(runtime);
        }
    }
    let runtime = Arc::new(
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("unable to build the Tokio runtime"),
    );
    if let Some((_, dead)) = slot.replace((pid, Arc::clone(&runtime))) {
        // The replaced runtime belongs to the parent process of a
        // fork. Its threads do not exist in this process, so it is
        // leaked on purpose. Dropping it would run shutdown against
        // that dead state for no benefit.
        std::mem::forget(dead);
    }
    runtime
}

/// The runtime the generic `pyo3-async-runtimes` bridge spawns onto.
/// Spawning resolves the fork aware runtime above at spawn time, so
/// an async call made in a forked child runs on the child's runtime
/// rather than on the dead pre-fork one.
struct ForkAwareRuntime;

impl pyo3_async_runtimes::generic::Runtime for ForkAwareRuntime {
    type JoinError = tokio::task::JoinError;
    type JoinHandle = tokio::task::JoinHandle<()>;

    fn spawn<F>(fut: F) -> Self::JoinHandle
    where
        F: Future<Output = ()> + Send + 'static,
    {
        shared_runtime().spawn(async move {
            fut.await;
        })
    }
}

impl pyo3_async_runtimes::generic::ContextExt for ForkAwareRuntime {
    fn scope<F, R>(
        _locals: pyo3_async_runtimes::TaskLocals,
        fut: F,
    ) -> Pin<Box<dyn Future<Output = R> + Send>>
    where
        F: Future<Output = R> + Send + 'static,
    {
        // The futures crossed here call no Python awaitables and read
        // no task locals. The bridge only needs the running loop,
        // which it captures itself when the awaitable is created.
        Box::pin(fut)
    }

    fn get_task_locals() -> Option<pyo3_async_runtimes::TaskLocals> {
        None
    }
}

fn future_into_py_fork_aware<'py, F, T>(py: Python<'py>, fut: F) -> PyResult<Bound<'py, PyAny>>
where
    F: Future<Output = PyResult<T>> + Send + 'static,
    T: for<'p> IntoPyObject<'p>,
{
    pyo3_async_runtimes::generic::future_into_py::<ForkAwareRuntime, F, T>(py, fut)
}

/// Translate a core error into a `PlacesError` with structured attributes
/// the Python layer uses to pick a concrete exception subclass. API errors
/// also carry the envelope `error_code`, the parsed `details`, and any
/// field or quota violations extracted from them (C6).
/// Record the first attribute attachment failure on an error being
/// translated (R4-15); later failures do not overwrite it.
fn record_failure(slot: &mut Option<String>, result: PyResult<()>) {
    if let Err(e) = result {
        if slot.is_none() {
            *slot = Some(e.to_string());
        }
    }
}

fn to_pyerr(py: Python<'_>, err: CoreError) -> PyErr {
    let pyerr = PyErr::new::<PlacesError, _>(err.to_string());
    let instance = pyerr.value(py);
    // Every attribute attachment is attempted and the first failure is
    // remembered (R4-15). On any failure the caller gets the one
    // defined fallback below, the plainest PlacesError carrying the
    // message and the attachment failure, instead of an exception
    // object whose attributes silently went missing one by one.
    let mut first_failure: Option<String> = None;
    record_failure(&mut first_failure, instance.setattr("kind", err.kind()));
    record_failure(
        &mut first_failure,
        instance.setattr("status_code", err.status_code()),
    );
    record_failure(
        &mut first_failure,
        instance.setattr("google_status", err.google_status()),
    );
    record_failure(
        &mut first_failure,
        instance.setattr("error_code", err.error_code()),
    );
    record_failure(
        &mut first_failure,
        instance.setattr("status_mismatch", err.status_mismatch()),
    );
    record_failure(
        &mut first_failure,
        instance.setattr("retryable", err.retryable()),
    );
    record_failure(
        &mut first_failure,
        instance.setattr("retry_after", err.retry_after()),
    );
    match serde_json::to_value(err.details())
        .map_err(|e| e.to_string())
        .and_then(|details| value_to_py(py, &details).map_err(|e| e.to_string()))
    {
        Ok(value) => record_failure(&mut first_failure, instance.setattr("details", value)),
        Err(e) => {
            if first_failure.is_none() {
                first_failure = Some(e);
            }
        }
    }
    let violations: Vec<(String, String)> = err.field_violations();
    match value_to_py(
        py,
        &serde_json::Value::Array(
            violations
                .iter()
                .map(|(field, description)| {
                    serde_json::json!({"field": field, "description": description})
                })
                .collect(),
        ),
    )
    .map_err(|e| e.to_string())
    {
        Ok(value) => record_failure(&mut first_failure, instance.setattr("field_violations", value)),
        Err(e) => {
            if first_failure.is_none() {
                first_failure = Some(e);
            }
        }
    }
    match value_to_py(py, &serde_json::Value::Array(err.quota_violations()))
        .map_err(|e| e.to_string())
    {
        Ok(value) => record_failure(
            &mut first_failure,
            instance.setattr("quota_violations", value),
        ),
        Err(e) => {
            if first_failure.is_none() {
                first_failure = Some(e);
            }
        }
    }
    if let Some(failure) = first_failure {
        return PyErr::new::<PlacesError, _>(format!(
            "{err} (error attributes could not be attached: {failure})"
        ));
    }
    pyerr
}

fn mask_from(py: Python<'_>, fields: Option<Vec<String>>) -> PyResult<Option<FieldMask>> {
    match fields {
        None => Ok(None),
        Some(paths) => FieldMask::new(paths).map(Some).map_err(|e| to_pyerr(py, e)),
    }
}

/// Body fields the typed requests declare as booleans, by wire name.
/// The generic converter below applies Python truthiness to these,
/// so the string "false" used to reach the API as true (R5-R2). The
/// conversion layer now accepts only a real bool (or None) for them,
/// which also covers dict-shaped parameters such as routing
/// parameters that the Python layer passes through. The walker
/// descends through dicts, lists and tuples up to a hard depth
/// bound (MAX_BODY_DEPTH); anything deeper, including the infinite
/// descent of a self-referential structure, is a config error
/// instead of a stack overflow in the host interpreter.
const BOOL_BODY_FIELDS: &[&str] = &[
    "openNow",
    "strictTypeFiltering",
    "includeQueryPredictions",
    "includePureServiceAreaBusinesses",
    "includeFutureOpeningBusinesses",
    "avoidTolls",
    "avoidHighways",
    "avoidFerries",
];

/// The deepest body nesting the conversion layer walks. Real Places
/// bodies nest a handful of levels; the bound exists so a cyclic or
/// absurdly deep caller structure fails as a typed error. The
/// generic converter in body_to_request only runs after this walk
/// passes, so it never sees a cycle either. (The other recursion in
/// this file, value_to_py, walks serde_json values built from the
/// core's own typed results, which are acyclic by construction and
/// not caller shaped.)
const MAX_BODY_DEPTH: usize = 128;

fn check_body_bools(value: &Bound<'_, PyAny>, depth: usize) -> Result<(), String> {
    if depth > MAX_BODY_DEPTH {
        return Err(format!(
            "request body is nested deeper than {MAX_BODY_DEPTH} levels; \
             check for a self-referential structure"
        ));
    }
    if let Ok(map) = value.downcast::<PyDict>() {
        for (key, item) in map.iter() {
            if let Ok(name) = key.extract::<String>() {
                if BOOL_BODY_FIELDS.contains(&name.as_str())
                    && !item.is_none()
                    && !item.is_instance_of::<PyBool>()
                {
                    // Same dialect as the Python layer's
                    // _validate_bool: the field name and the
                    // offending value's repr.
                    let shown = item
                        .repr()
                        .map(|repr| repr.to_string())
                        .unwrap_or_else(|_| item.get_type().to_string());
                    return Err(format!("{name} must be a bool, got {shown}"));
                }
            }
            check_body_bools(&item, depth + 1)?;
        }
    } else if let Ok(list) = value.downcast::<PyList>() {
        for item in list.iter() {
            check_body_bools(&item, depth + 1)?;
        }
    } else if let Ok(tuple) = value.downcast::<PyTuple>() {
        for item in tuple.iter() {
            check_body_bools(&item, depth + 1)?;
        }
    }
    Ok(())
}

fn body_to_request<T>(body: &Bound<'_, PyDict>) -> PyResult<T>
where
    T: serde::de::DeserializeOwned,
{
    if let Err(detail) = check_body_bools(body.as_any(), 0) {
        return Err(to_pyerr(body.py(), CoreError::Config { detail }));
    }
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
    // Converted by hand rather than through a generic converter
    // (R4-19): with arbitrary precision numbers, a serde_json Number
    // serializes through a private envelope shape that generic
    // converters hand back as a dict, so every numeric field broke.
    // Here an integer keeps its exact value at any size (Python ints
    // are arbitrary precision too) and a float stays a float.
    match value {
        Value::Null => Ok(py.None()),
        Value::Bool(b) => Ok(b.into_pyobject(py)?.to_owned().unbind().into_any()),
        Value::Number(n) => number_to_py(py, n),
        Value::String(s) => Ok(s.as_str().into_pyobject(py)?.unbind().into_any()),
        Value::Array(items) => {
            let list = pyo3::types::PyList::empty(py);
            for item in items {
                list.append(value_to_py(py, item)?)?;
            }
            Ok(list.unbind().into_any())
        }
        Value::Object(map) => {
            let dict = PyDict::new(py);
            for (key, item) in map {
                dict.set_item(key, value_to_py(py, item)?)?;
            }
            Ok(dict.unbind().into_any())
        }
    }
}

fn number_to_py(py: Python<'_>, n: &serde_json::Number) -> PyResult<PyObject> {
    if let Some(i) = n.as_i64() {
        return Ok(i.into_pyobject(py)?.unbind().into_any());
    }
    if let Some(u) = n.as_u64() {
        return Ok(u.into_pyobject(py)?.unbind().into_any());
    }
    let text = n.to_string();
    if !text.contains(['.', 'e', 'E']) {
        // An integer beyond u64: Python's int parses the exact
        // decimal text, so no digit is lost on the way across. Past
        // the interpreter's string conversion limit (4300 digits by
        // default) that parse refuses with a ValueError, and the
        // refusal must not escape as a bare builtin outside the
        // exception hierarchy (red team R1): it is a decode failure
        // of this layer, like every other conversion failure here.
        let builtins = pyo3::types::PyModule::import(py, "builtins")?;
        return match builtins.getattr("int")?.call1((text.clone(),)) {
            Ok(value) => Ok(value.unbind()),
            Err(_) => Err(to_pyerr(
                py,
                CoreError::Decode {
                    detail: format!(
                        "an integer in the response carries {} digits, beyond the interpreter limit for exact conversion",
                        text.trim_start_matches('-').len()
                    ),
                    status: None,
                    source: None,
                },
            )),
        };
    }
    Ok(n.as_f64()
        .unwrap_or(f64::NAN)
        .into_pyobject(py)?
        .unbind()
        .into_any())
}

/// A JSON result crosses the boundary as a 3-tuple of the typed
/// dict, the response body text and the HTTP status (Round 16).
/// Attributes decode from the typed dict, exactly as they did when
/// the dict was the only payload. The Python layer parses the body
/// once and builds raw at every model level from it, which is what
/// makes raw the wire payload verbatim through the client. The
/// status rides along so a Python side conversion failure can
/// carry the status of the response it failed on.
fn result_to_py<T>(
    py: Python<'_>,
    result: Result<(T, String, u16), CoreError>,
) -> PyResult<PyObject>
where
    T: serde::Serialize,
{
    match result {
        Ok((value, body, status)) => {
            let json = serde_json::to_value(&value).map_err(|e| {
                to_pyerr(
                    py,
                    CoreError::Decode {
                        detail: e.to_string(),
                        status: None,
                        source: Some(Box::new(e)),
                    },
                )
            })?;
            let typed = value_to_py(py, &json)?;
            let body = body.into_pyobject(py)?.unbind().into_any();
            let status = status.into_pyobject(py)?.unbind().into_any();
            let tuple = PyTuple::new(py, [typed, body, status])?;
            Ok(tuple.unbind().into_any())
        }
        Err(e) => Err(to_pyerr(py, e)),
    }
}

/// Photo results cross the boundary as a tagged 4-tuple so the Python
/// layer can tell the two wire forms apart: `("bytes", content, content
/// type, status)` for the downloaded image, `("uri", typed, body,
/// status)` when the redirect was skipped and the endpoint answered
/// with JSON, where typed is the typed form as a dict (the attribute
/// source) and body is the response body text (the raw source), the
/// same split the JSON endpoints cross with. The status rides as the
/// fourth element of both arms so a Python side conversion failure
/// can carry it.
/// A photo result conversion failure is a decode failure of this
/// layer (R4-22), reported inside the exception hierarchy like every
/// other conversion failure here, never as a bare PyValueError.
fn photo_conversion_err(py: Python<'_>, e: impl std::fmt::Display) -> PyErr {
    to_pyerr(
        py,
        CoreError::Decode {
            detail: e.to_string(),
            status: None,
            source: None,
        },
    )
}

fn photo_to_py(
    py: Python<'_>,
    result: Result<(placekit_core::models::PhotoMedia, Option<String>, u16), CoreError>,
) -> PyResult<PyObject> {
    match result {
        Ok((placekit_core::models::PhotoMedia::Bytes(photo), _, status)) => {
            let tag = "bytes"
                .into_pyobject(py)
                .map_err(|e| photo_conversion_err(py, e))?
                .unbind()
                .into_any();
            let bytes = PyBytes::new(py, &photo.bytes).unbind().into_any();
            let content_type = photo
                .content_type
                .into_pyobject(py)
                .map_err(|e| photo_conversion_err(py, e))?
                .unbind()
                .into_any();
            let status = status
                .into_pyobject(py)
                .map_err(|e| photo_conversion_err(py, e))?
                .unbind()
                .into_any();
            let tuple = PyTuple::new(py, [tag, bytes, content_type, status])
                .map_err(|e| photo_conversion_err(py, e))?;
            Ok(tuple.unbind().into_any())
        }
        Ok((placekit_core::models::PhotoMedia::Uri(media), body, status)) => {
            let tag = "uri"
                .into_pyobject(py)
                .map_err(|e| photo_conversion_err(py, e))?
                .unbind()
                .into_any();
            // The typed dict crosses as the attribute source, like on
            // the JSON endpoints. PhotoMediaJson flattens what the
            // core does not type into its extra map, so the dict
            // carries the whole JSON form in typed shape. The body
            // text the core held beside the decode crosses with it as
            // the raw source. The core returns the body on this form
            // by construction. An absent body is a conversion failure
            // of this layer, never an empty raw.
            let json = serde_json::to_value(&media).map_err(|e| photo_conversion_err(py, e))?;
            let typed = value_to_py(py, &json).map_err(|e| photo_conversion_err(py, e))?;
            let body = body.ok_or_else(|| {
                photo_conversion_err(py, "photo URI result carried no response body")
            })?;
            let body = body
                .into_pyobject(py)
                .map_err(|e| photo_conversion_err(py, e))?
                .unbind()
                .into_any();
            let status = status
                .into_pyobject(py)
                .map_err(|e| photo_conversion_err(py, e))?
                .unbind()
                .into_any();
            let tuple = PyTuple::new(py, [tag, typed, body, status])
                .map_err(|e| photo_conversion_err(py, e))?;
            Ok(tuple.unbind().into_any())
        }
        Err(e) => Err(to_pyerr(py, e)),
    }
}

fn build_core_client(
    api_key: &str,
    base_url: Option<&str>,
    timeout: Option<f64>,
) -> Result<CoreClient, CoreError> {
    let mut builder = CoreClient::builder(api_key);
    if let Some(base_url) = base_url {
        builder = builder.base_url(base_url);
    }
    if let Some(timeout) = timeout {
        builder = builder.timeout(std::time::Duration::from_secs_f64(timeout));
    }
    builder.build()
}

/// The Rust client handle wrapped for Python.
///
/// The handle keeps its construction inputs beside the built client
/// so a forked child can rebuild the client for its own process. A
/// client built before a fork carries a connection pool whose state
/// belongs to the parent process and its dead runtime generation.
/// Reusing it in the child stalls against that state. The first call
/// under a new process id therefore builds a fresh client from the
/// retained inputs, and the inherited client is leaked rather than
/// dropped, like the runtime it belonged with.
#[pyclass(name = "Client")]
struct PyClient {
    api_key: String,
    base_url: Option<String>,
    timeout: Option<f64>,
    current: Mutex<(u32, Arc<CoreClient>)>,
}

impl PyClient {
    /// The core client for this process, rebuilt after a fork.
    fn handle(&self, py: Python<'_>) -> PyResult<Arc<CoreClient>> {
        let pid = std::process::id();
        let mut current = self
            .current
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if current.0 == pid {
            return Ok(Arc::clone(&current.1));
        }
        let client = build_core_client(&self.api_key, self.base_url.as_deref(), self.timeout)
            .map_err(|e| to_pyerr(py, e))?;
        let rebuilt = Arc::new(client);
        let (_, inherited) = std::mem::replace(&mut *current, (pid, Arc::clone(&rebuilt)));
        std::mem::forget(inherited);
        Ok(rebuilt)
    }
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
        if let Some(timeout) = timeout {
            // One rule everywhere (R4-04): the same 3600 second cap
            // the Python wrapper documents, applied here so direct
            // native consumers get it too. The bound also keeps the
            // value far from the range where Duration::from_secs_f64
            // panics (at or above 2^64 seconds), which used to escape
            // as a PanicException outside the exception hierarchy.
            if !timeout.is_finite() || timeout <= 0.0 || timeout > 3600.0 {
                return Err(PyValueError::new_err(
                    "timeout must be a positive, finite number of seconds, at most 3600",
                ));
            }
        }
        let client =
            build_core_client(&api_key, base_url.as_deref(), timeout).map_err(|e| {
                match e.kind() {
                    "config" => PyValueError::new_err(e.to_string()),
                    _ => to_pyerr(py, e),
                }
            })?;
        Ok(Self {
            api_key,
            base_url,
            timeout,
            current: Mutex::new((std::process::id(), Arc::new(client))),
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
        let inner = self.handle(py)?;
        let result = py.allow_threads(|| {
            shared_runtime()
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
        let inner = self.handle(py)?;
        future_into_py_fork_aware(py, async move {
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
        let inner = self.handle(py)?;
        let result = py.allow_threads(|| {
            shared_runtime()
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
        let inner = self.handle(py)?;
        future_into_py_fork_aware(py, async move {
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
        let inner = self.handle(py)?;
        let result = py.allow_threads(|| {
            shared_runtime().block_on(async move {
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
        let inner = self.handle(py)?;
        future_into_py_fork_aware(py, async move {
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
        let inner = self.handle(py)?;
        let result = py.allow_threads(|| {
            shared_runtime()
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
        let inner = self.handle(py)?;
        future_into_py_fork_aware(py, async move {
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
        let inner = self.handle(py)?;
        let result = py.allow_threads(|| {
            shared_runtime().block_on(async move {
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
        let inner = self.handle(py)?;
        future_into_py_fork_aware(py, async move {
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
