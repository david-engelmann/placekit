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
//! The runtime is process wide but fork aware. A runtime built
//! before a fork is dead in the child because its worker threads do
//! not survive the fork. These bindings therefore keep their own
//! runtime, keyed by the process id it was built under. The first
//! call a forked child makes builds a fresh runtime for its own
//! process id, and the dead parent runtime is leaked rather than
//! dropped, so no shutdown machinery ever runs against threads that
//! no longer exist.
//!
//! An async call spawns its core future onto that runtime and hands
//! the Python layer a call handle. The future completes into Rust
//! state only, and the Python layer collects the stored result from
//! its own event loop thread. No runtime worker thread ever touches
//! a Python object. Round 30 removed the `pyo3-async-runtimes`
//! bridge from this path after its per call completion tasks were
//! shown to crash processes during interpreter exit. The bridge
//! finished every call by taking the GIL on a worker thread and
//! delivering the result through the event loop from there, and at
//! exit that machinery was still entangled with the interpreter
//! while finalization dismantled it.

use std::future::Future;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use futures_util::FutureExt;
use placekit_core::models::{
    AutocompleteRequest, NearbySearchRequest, PhotoMedia, TextSearchRequest,
};
use placekit_core::{Client as CoreClient, ComponentData, Error as CoreError, FieldMask};
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

/// The text of a panic payload, for error messages that must name
/// what panicked. Panics raised by Rust code carry a string payload;
/// anything else is reported as carrying no message.
fn panic_payload_text(payload: &(dyn std::any::Any + Send)) -> String {
    if let Some(text) = payload.downcast_ref::<&str>() {
        (*text).to_owned()
    } else if let Some(text) = payload.downcast_ref::<String>() {
        text.clone()
    } else {
        "a panic with no message payload".to_owned()
    }
}

/// The typed error a runtime panic surfaces as (Round 23). A panic
/// from the runtime machinery is a transport side failure with no
/// HTTP response behind it, so it takes the network class, and its
/// message names the panic payload the caller would otherwise never
/// see.
fn runtime_panic_error(payload: &(dyn std::any::Any + Send)) -> CoreError {
    CoreError::Network {
        detail: format!(
            "the Tokio runtime panicked while running a call: {}",
            panic_payload_text(payload)
        ),
        source: None,
    }
}

fn shared_runtime() -> Result<Arc<tokio::runtime::Runtime>, CoreError> {
    let pid = std::process::id();
    let mut slot = PROCESS_RUNTIME
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    if let Some((built_pid, runtime)) = slot.as_ref() {
        if *built_pid == pid {
            return Ok(Arc::clone(runtime));
        }
    }
    // The build is fallible twice over (Round 23): Builder::build
    // reports an error when the operating system refuses part of the
    // setup, and the worker launch inside the build can panic on a
    // thread refusal, which the red team produced live. Both shapes
    // land in the typed hierarchy here, where the build used to rest
    // on an expect whose panic crossed the PyO3 boundary as a
    // PanicException outside the hierarchy.
    let runtime = match std::panic::catch_unwind(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
    }) {
        Ok(Ok(runtime)) => Arc::new(runtime),
        Ok(Err(e)) => {
            return Err(CoreError::Network {
                detail: format!("could not build the Tokio runtime: {e}"),
                source: Some(Box::new(e)),
            });
        }
        Err(payload) => {
            return Err(CoreError::Network {
                detail: format!(
                    "could not build the Tokio runtime: {}",
                    panic_payload_text(&*payload)
                ),
                source: None,
            });
        }
    };
    if let Some((_, dead)) = slot.replace((pid, Arc::clone(&runtime))) {
        // The replaced runtime belongs to the parent process of a
        // fork. Its threads do not exist in this process, so it is
        // leaked on purpose. Dropping it would run shutdown against
        // that dead state for no benefit.
        std::mem::forget(dead);
    }
    Ok(runtime)
}

/// Run a core future on the shared runtime for a sync method,
/// keeping every failure inside the typed error hierarchy
/// (Round 23). A build failure returns from [`shared_runtime`] as a
/// typed error, and a panic raised while the runtime drives the
/// future is caught and returned as a network class error naming
/// the panic payload, where it used to cross the PyO3 boundary as a
/// PanicException.
fn block_on_guarded<F, T>(fut: F) -> Result<T, CoreError>
where
    F: Future<Output = Result<T, CoreError>>,
{
    let runtime = shared_runtime()?;
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| runtime.block_on(fut))) {
        Ok(result) => result,
        Err(payload) => Err(runtime_panic_error(&*payload)),
    }
}

/// Run a core future for an async method under a panic guard
/// (Round 23). A panic raised while the future is polled is caught
/// and returned as a network class error naming the panic payload,
/// matching the sync side's [`block_on_guarded`], where it used to
/// fail the spawned task and surface outside the typed hierarchy.
async fn run_guarded<F, T>(fut: F) -> Result<T, CoreError>
where
    F: Future<Output = Result<T, CoreError>>,
{
    match std::panic::AssertUnwindSafe(fut).catch_unwind().await {
        Ok(result) => result,
        Err(payload) => Err(runtime_panic_error(&*payload)),
    }
}

/// The stored output of one async call. The typed response is
/// serialized on the runtime worker that ran the call, which is
/// pure Rust work, and converted into Python objects later on the
/// thread that collects the result. Photo responses carry no
/// serialization step and move as they are.
enum CallOutput {
    Json(Result<(serde_json::Value, String, u16), CoreError>),
    Photo(Result<(PhotoMedia, Option<String>, u16), CoreError>),
}

/// Serialize a JSON call result for storage in a call handle. A
/// value that fails to serialize fails the call with the same
/// decode error the sync path raises for it in [`result_to_py`].
///
/// The conversion runs under the same panic guard discipline as
/// the core future (Round 33, Info 9). It executes inside the
/// spawned task after [`run_guarded`] returns, so a panic there
/// would unwind the task before [`start_call`] writes the slot
/// or sets the done flag, and the Python pump would poll the
/// handle until the caller cancelled. A panic now settles the
/// call with the same network class error a guarded core panic
/// produces, so the slot is always written and the handle
/// always completes.
fn stored_json<T>(result: Result<(T, String, u16), CoreError>) -> CallOutput
where
    T: serde::Serialize,
{
    let stored = match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        result.and_then(|(value, body, status)| {
            serde_json::to_value(&value)
                .map(|json| (json, body, status))
                .map_err(|e| CoreError::Decode {
                    detail: e.to_string(),
                    status: None,
                    source: Some(Box::new(e)),
                })
        })
    })) {
        Ok(stored) => stored,
        Err(payload) => Err(runtime_panic_error(&*payload)),
    };
    CallOutput::Json(stored)
}

/// The completion slot one async call writes exactly once, on the
/// runtime worker that ran the call. It holds only Rust state, so
/// writing it and later dropping it are safe on any thread at any
/// point in the life of the process, including interpreter exit.
struct CallSlot {
    output: Mutex<Option<CallOutput>>,
    done: AtomicBool,
}

/// The handle an async method returns for one in flight call
/// (Round 30). The Python layer polls `is_done` from its event loop
/// thread and collects a finished call with `take_result`, so every
/// Python object for the call is built and destroyed on Python
/// threads. Dropping the handle aborts the call, which mirrors the
/// cancellation a dropped in flight call used to get and keeps a
/// forgotten handle from holding its request past the loop that
/// owned it.
#[pyclass(name = "CallHandle")]
struct PyCallHandle {
    slot: Arc<CallSlot>,
    join: Mutex<Option<tokio::task::JoinHandle<()>>>,
}

impl Drop for PyCallHandle {
    fn drop(&mut self) {
        self.abort_join();
    }
}

impl PyCallHandle {
    fn abort_join(&self) {
        let taken = match self.join.lock() {
            Ok(mut guard) => guard.take(),
            Err(poisoned) => poisoned.into_inner().take(),
        };
        if let Some(join) = taken {
            join.abort();
        }
    }
}

#[pymethods]
impl PyCallHandle {
    /// Whether the call has finished and its output is stored.
    fn is_done(&self) -> bool {
        self.slot.done.load(Ordering::SeqCst)
    }

    /// Collect the stored output of a finished call, converting it
    /// to Python objects on this thread. Runs exactly once per
    /// finished call from the Python layer. A call with no stored
    /// output fails with a decode class error rather than a panic.
    fn take_result(&self, py: Python<'_>) -> PyResult<PyObject> {
        let output = match self.slot.output.lock() {
            Ok(mut guard) => guard.take(),
            Err(poisoned) => poisoned.into_inner().take(),
        };
        match output {
            Some(CallOutput::Json(Ok((json, body, status)))) => {
                json_tuple_to_py(py, &json, body, status)
            }
            Some(CallOutput::Json(Err(err))) => Err(to_pyerr(py, err)),
            Some(CallOutput::Photo(result)) => photo_to_py(py, result),
            None => Err(to_pyerr(
                py,
                CoreError::Decode {
                    detail: "call result is not ready or was already collected".to_string(),
                    status: None,
                    source: None,
                },
            )),
        }
    }

    /// Abort the call if it is still running. The stored output of
    /// a call that already finished is left in place.
    fn abort(&self) {
        self.abort_join();
    }
}

/// Spawn one async call onto the shared runtime and return its
/// handle. The runtime is resolved here on a fallible path first
/// (Round 23), so a build failure raises as a typed error from the
/// calling method rather than a panic inside spawn machinery that
/// cannot return one.
fn start_call<F>(py: Python<'_>, fut: F) -> PyResult<PyCallHandle>
where
    F: Future<Output = CallOutput> + Send + 'static,
{
    let runtime = shared_runtime().map_err(|err| to_pyerr(py, err))?;
    let slot = Arc::new(CallSlot {
        output: Mutex::new(None),
        done: AtomicBool::new(false),
    });
    let task_slot = Arc::clone(&slot);
    let join = runtime.spawn(async move {
        let output = fut.await;
        match task_slot.output.lock() {
            Ok(mut guard) => *guard = Some(output),
            Err(poisoned) => *poisoned.into_inner() = Some(output),
        }
        task_slot.done.store(true, Ordering::SeqCst);
    });
    Ok(PyCallHandle {
        slot,
        join: Mutex::new(Some(join)),
    })
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
    // The details surface (the parsed details and the field and
    // quota views extracted from them) converts as one surface,
    // and it is best effort diagnostic payload rather than
    // classification. A value inside it that this layer cannot
    // convert, an integer literal past the interpreter's exact
    // conversion limit is the proven shape (Round 41, Finding 3),
    // used to count as an attachment failure like any other, so
    // the fallback below demoted the whole error to the plainest
    // PlacesError and the caller lost the class, the Google
    // status, the error code and the retryable flag the core had
    // classified, for the sake of the payload. The surface now
    // degrades to empty instead and records no failure, so the
    // classification attributes attached above stand exactly as
    // classified while the details and both views read empty for
    // that call.
    let details_result = serde_json::to_value(err.details())
        .map_err(|e| e.to_string())
        .and_then(|details| value_to_py(py, &details).map_err(|e| e.to_string()));
    let field_violations_result =
        value_to_py(py, &serde_json::Value::Array(err.field_violations()))
            .map_err(|e| e.to_string());
    let quota_violations_result =
        value_to_py(py, &serde_json::Value::Array(err.quota_violations()))
            .map_err(|e| e.to_string());
    match (
        details_result,
        field_violations_result,
        quota_violations_result,
    ) {
        (Ok(details), Ok(field_violations), Ok(quota_violations)) => {
            record_failure(&mut first_failure, instance.setattr("details", details));
            record_failure(
                &mut first_failure,
                instance.setattr("field_violations", field_violations),
            );
            record_failure(
                &mut first_failure,
                instance.setattr("quota_violations", quota_violations),
            );
        }
        _ => {
            let empty = || pyo3::types::PyList::empty(py).unbind().into_any();
            record_failure(&mut first_failure, instance.setattr("details", empty()));
            record_failure(
                &mut first_failure,
                instance.setattr("field_violations", empty()),
            );
            record_failure(
                &mut first_failure,
                instance.setattr("quota_violations", empty()),
            );
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

/// One address component as the Python layer hands it over, a
/// `(long_text, short_text, types)` triple of plain values. The
/// Python `placekit.address` module validates and materialises
/// caller values through its own funnels first, so what arrives
/// here is already checked data and the conversion into the
/// core's [`ComponentData`] cannot fail on shape.
///
/// Texts cross as byte strings in the form the Python layer's
/// surrogatepass codec produces, so a text carrying a lone
/// surrogate reaches the core exactly and comes back exactly,
/// where a Rust `String` crossing could not encode it at all.
type PyComponent = (Option<Vec<u8>>, Option<Vec<u8>>, Vec<Option<Vec<u8>>>);

fn components_from(py_components: Vec<PyComponent>) -> Vec<ComponentData> {
    py_components
        .into_iter()
        .map(|(long_text, short_text, types)| ComponentData {
            long_text,
            short_text,
            types,
        })
        .collect()
}

/// A city resolution as a plain tuple for the Python layer to
/// wrap in its `CityResolution` dataclass, in field order. Text
/// fields cross as byte strings on the same terms as the
/// component texts, and the carrier and confidence names cross
/// as plain strings because the core mints them itself.
type PyCityResolution = (
    Option<Vec<u8>>,
    Option<String>,
    String,
    Option<Vec<u8>>,
    Option<Vec<u8>>,
    Option<String>,
);

/// A district resolution as a plain tuple for the Python layer
/// to wrap in its `DistrictResolution` dataclass, in field
/// order, on the same crossing terms as the city row.
type PyDistrictResolution = (Option<Vec<u8>>, Option<String>, String, Option<Vec<u8>>);

fn city_to_py(resolution: placekit_core::address::CityResolution) -> PyCityResolution {
    (
        resolution.value,
        resolution.carrier.map(str::to_owned),
        resolution.confidence.to_owned(),
        resolution.country_code,
        resolution.competing_value,
        resolution.competing_carrier.map(str::to_owned),
    )
}

/// The indices of every component whose types contain the name.
#[pyfunction]
fn address_matching_indices(components: Vec<PyComponent>, type_name: Vec<u8>) -> Vec<usize> {
    placekit_core::address::matching_indices(&components_from(components), &type_name)
}

/// The indices of every component whose types list is empty.
#[pyfunction]
fn address_untyped_indices(components: Vec<PyComponent>) -> Vec<usize> {
    placekit_core::address::untyped_indices(&components_from(components))
}

/// The first nonempty long text among the matches for a type.
#[pyfunction]
fn address_first_long_text(components: Vec<PyComponent>, type_name: Vec<u8>) -> Option<Vec<u8>> {
    placekit_core::address::first_long_text(&components_from(components), &type_name)
}

/// The index of the component the first nonempty long text
/// among the matches for a type sits on, so the Python layer
/// can hand back the caller component's own text object.
#[pyfunction]
fn address_first_long_text_index(
    components: Vec<PyComponent>,
    type_name: Vec<u8>,
) -> Option<usize> {
    placekit_core::address::first_long_text_index(&components_from(components), &type_name)
}

/// The first nonempty short text among the matches for a type.
#[pyfunction]
fn address_first_short_text(components: Vec<PyComponent>, type_name: Vec<u8>) -> Option<Vec<u8>> {
    placekit_core::address::first_short_text(&components_from(components), &type_name)
}

/// The nonempty long texts of every match, in list order.
#[pyfunction]
fn address_long_texts(components: Vec<PyComponent>, type_name: Vec<u8>) -> Vec<Vec<u8>> {
    placekit_core::address::long_texts(&components_from(components), &type_name)
}

/// The nonempty short texts of every match, in list order.
#[pyfunction]
fn address_short_texts(components: Vec<PyComponent>, type_name: Vec<u8>) -> Vec<Vec<u8>> {
    placekit_core::address::short_texts(&components_from(components), &type_name)
}

/// The short text of the first country component with one.
#[pyfunction]
fn address_country_code(components: Vec<PyComponent>) -> Option<Vec<u8>> {
    placekit_core::address::country_code_from_components(&components_from(components))
}

/// Every city reading for one component set and country code.
///
/// The last two arguments carry the lazy read state the core
/// documents. `postal_locality_read` false says the field has
/// not been read yet, and the answer then comes back as
/// `(true, [])` when the chain reaches the postal carrier, so
/// the Python layer reads the field at exactly the point the
/// old implementation read it and calls again with the flag set
/// and the read value (or `None`) in hand.
#[pyfunction]
#[pyo3(signature = (components, postal_locality_read, country_code, postal_locality))]
fn address_city_resolutions(
    components: Vec<PyComponent>,
    postal_locality_read: bool,
    country_code: Option<Vec<u8>>,
    postal_locality: Option<Vec<u8>>,
) -> (bool, Vec<PyCityResolution>) {
    let postal = if postal_locality_read {
        placekit_core::address::PostalLocality::Read(postal_locality)
    } else {
        placekit_core::address::PostalLocality::Unread
    };
    match placekit_core::address::city_resolutions(
        &components_from(components),
        country_code.as_deref(),
        &postal,
    ) {
        placekit_core::address::CityResolutions::Done(done) => {
            (false, done.into_iter().map(city_to_py).collect())
        }
        placekit_core::address::CityResolutions::NeedsPostalLocality => (true, Vec::new()),
    }
}

/// The district reading for one component set and country code,
/// as a `(value, carrier, confidence, country_code)` tuple.
#[pyfunction]
#[pyo3(signature = (components, country_code))]
fn address_district_resolution(
    components: Vec<PyComponent>,
    country_code: Option<Vec<u8>>,
) -> PyDistrictResolution {
    let district = placekit_core::address::district_resolution(
        &components_from(components),
        country_code.as_deref(),
    );
    (
        district.value,
        district.carrier.map(str::to_owned),
        district.confidence.to_owned(),
        district.country_code,
    )
}

/// The postal code reading composed from the two carrier
/// values, as a `(value, carrier, status, country_code,
/// competing_value, competing_carrier)` tuple.
#[pyfunction]
#[pyo3(signature = (country_code, component_value, postal_value))]
fn address_postal_code_result(
    country_code: Option<Vec<u8>>,
    component_value: Option<Vec<u8>>,
    postal_value: Option<Vec<u8>>,
) -> PyCityResolution {
    let result =
        placekit_core::address::postal_code_result(country_code, component_value, postal_value);
    (
        result.value,
        result.carrier.map(str::to_owned),
        result.status.to_owned(),
        result.country_code,
        result.competing_value,
        result.competing_carrier.map(str::to_owned),
    )
}

/// The component level presence flags for one component set, as
/// a `(has_street_number, has_route, has_premise, has_subpremise,
/// is_premise_level, spans_multiple_routes, has_no_street_level)`
/// tuple.
#[pyfunction]
fn address_component_flags(
    components: Vec<PyComponent>,
) -> (bool, bool, bool, bool, bool, bool, bool) {
    let flags = placekit_core::address::component_flags(&components_from(components));
    (
        flags.has_street_number,
        flags.has_route,
        flags.has_premise,
        flags.has_subpremise,
        flags.is_premise_level,
        flags.spans_multiple_routes,
        flags.has_no_street_level,
    )
}

/// Split a compound plus code at its first space, returning the
/// `(code_part, locality_text)` pair or `None` when the input is
/// not a compound form.
#[pyfunction]
fn address_split_compound_code(compound_code: Vec<u8>) -> Option<(Vec<u8>, Vec<u8>)> {
    placekit_core::address::split_compound_code(&compound_code)
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

/// Convert one stored JSON call output into the Python result
/// tuple. Shared by the sync path through [`result_to_py`] and by
/// call handle collection, so both paths build the identical tuple.
fn json_tuple_to_py(py: Python<'_>, json: &Value, body: String, status: u16) -> PyResult<PyObject> {
    let typed = value_to_py(py, json)?;
    let body = body.into_pyobject(py)?.unbind().into_any();
    let status = status.into_pyobject(py)?.unbind().into_any();
    let tuple = PyTuple::new(py, [typed, body, status])?;
    Ok(tuple.unbind().into_any())
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
            json_tuple_to_py(py, &json, body, status)
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
            block_on_guarded(async move { inner.text_search(&request, mask.as_ref()).await })
        });
        result_to_py(py, result)
    }

    #[pyo3(signature = (body, fields=None))]
    fn text_search_async(
        &self,
        py: Python<'_>,
        body: Bound<'_, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<PyCallHandle> {
        let request: TextSearchRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.handle(py)?;
        start_call(py, async move {
            let result = run_guarded(inner.text_search(&request, mask.as_ref())).await;
            stored_json(result)
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
            block_on_guarded(async move { inner.nearby_search(&request, mask.as_ref()).await })
        });
        result_to_py(py, result)
    }

    #[pyo3(signature = (body, fields=None))]
    fn nearby_search_async(
        &self,
        py: Python<'_>,
        body: Bound<'_, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<PyCallHandle> {
        let request: NearbySearchRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.handle(py)?;
        start_call(py, async move {
            let result = run_guarded(inner.nearby_search(&request, mask.as_ref())).await;
            stored_json(result)
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
            block_on_guarded(async move {
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
    fn place_details_async(
        &self,
        py: Python<'_>,
        place_id: String,
        fields: Option<Vec<String>>,
        language_code: Option<String>,
        region_code: Option<String>,
        session_token: Option<String>,
    ) -> PyResult<PyCallHandle> {
        let mask = mask_from(py, fields)?;
        let inner = self.handle(py)?;
        start_call(py, async move {
            let result = run_guarded(inner.place_details(
                &place_id,
                mask.as_ref(),
                language_code.as_deref(),
                region_code.as_deref(),
                session_token.as_deref(),
            ))
            .await;
            stored_json(result)
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
            block_on_guarded(async move { inner.autocomplete(&request, mask.as_ref()).await })
        });
        result_to_py(py, result)
    }

    #[pyo3(signature = (body, fields=None))]
    fn autocomplete_async(
        &self,
        py: Python<'_>,
        body: Bound<'_, PyDict>,
        fields: Option<Vec<String>>,
    ) -> PyResult<PyCallHandle> {
        let request: AutocompleteRequest = body_to_request(&body)?;
        let mask = mask_from(py, fields)?;
        let inner = self.handle(py)?;
        start_call(py, async move {
            let result = run_guarded(inner.autocomplete(&request, mask.as_ref())).await;
            stored_json(result)
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
            block_on_guarded(async move {
                inner
                    .place_photo(&photo_name, max_width_px, max_height_px, skip_http_redirect)
                    .await
            })
        });
        photo_to_py(py, result)
    }

    #[pyo3(signature = (photo_name, max_width_px=None, max_height_px=None, skip_http_redirect=false))]
    fn place_photo_async(
        &self,
        py: Python<'_>,
        photo_name: String,
        max_width_px: Option<u32>,
        max_height_px: Option<u32>,
        skip_http_redirect: bool,
    ) -> PyResult<PyCallHandle> {
        let inner = self.handle(py)?;
        start_call(py, async move {
            let result = run_guarded(inner.place_photo(
                &photo_name,
                max_width_px,
                max_height_px,
                skip_http_redirect,
            ))
            .await;
            CallOutput::Photo(result)
        })
    }
}

#[pymodule]
fn _placekit(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyClient>()?;
    m.add_class::<PyCallHandle>()?;
    m.add("PlacesError", m.py().get_type::<PlacesError>())?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(address_matching_indices, m)?)?;
    m.add_function(wrap_pyfunction!(address_untyped_indices, m)?)?;
    m.add_function(wrap_pyfunction!(address_first_long_text, m)?)?;
    m.add_function(wrap_pyfunction!(address_first_long_text_index, m)?)?;
    m.add_function(wrap_pyfunction!(address_first_short_text, m)?)?;
    m.add_function(wrap_pyfunction!(address_long_texts, m)?)?;
    m.add_function(wrap_pyfunction!(address_short_texts, m)?)?;
    m.add_function(wrap_pyfunction!(address_country_code, m)?)?;
    m.add_function(wrap_pyfunction!(address_city_resolutions, m)?)?;
    m.add_function(wrap_pyfunction!(address_district_resolution, m)?)?;
    m.add_function(wrap_pyfunction!(address_postal_code_result, m)?)?;
    m.add_function(wrap_pyfunction!(address_component_flags, m)?)?;
    m.add_function(wrap_pyfunction!(address_split_compound_code, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A value whose serialization panics, standing in for the
    /// conversion panic Round 33 Info 9 records as not
    /// constructible through the shipped response types. Test
    /// only: no production code path builds one.
    struct PanickingValue;

    impl serde::Serialize for PanickingValue {
        fn serialize<S>(&self, _serializer: S) -> Result<S::Ok, S::Error>
        where
            S: serde::Serializer,
        {
            panic!("synthetic serialization panic for the guard pin")
        }
    }

    /// The pin for the Round 33 repair. A panic inside the
    /// stored form conversion settles the call as the network
    /// class runtime panic error instead of unwinding, so the
    /// completion slot is written and the handle completes.
    /// Against the unguarded conversion this test fails by the
    /// panic escaping `stored_json` itself.
    #[test]
    fn stored_json_settles_a_serialization_panic_as_the_runtime_panic_error() {
        let output = stored_json(Ok((PanickingValue, String::new(), 200)));
        match output {
            CallOutput::Json(Err(CoreError::Network { detail, .. })) => {
                assert!(
                    detail.contains("synthetic serialization panic for the guard pin"),
                    "{detail}"
                );
            }
            _ => panic!("a conversion panic must settle as the runtime panic error"),
        }
    }

    /// The ordinary shapes the guard leaves untouched: a value
    /// that serializes is stored with its body and status, and a
    /// core error passes through as itself.
    #[test]
    fn stored_json_keeps_the_ordinary_shapes() {
        let mut value = serde_json::Map::new();
        value.insert("id".to_string(), Value::from("places/test"));
        match stored_json(Ok((Value::Object(value), "body".to_string(), 200))) {
            CallOutput::Json(Ok((json, body, status))) => {
                assert_eq!(json["id"], Value::from("places/test"));
                assert_eq!(body, "body");
                assert_eq!(status, 200);
            }
            _ => panic!("a serializable value must be stored whole"),
        }
        let err = CoreError::Decode {
            detail: "boom".to_string(),
            status: None,
            source: None,
        };
        match stored_json::<Value>(Err(err)) {
            CallOutput::Json(Err(CoreError::Decode { detail, .. })) => {
                assert_eq!(detail, "boom");
            }
            _ => panic!("a core error must pass through as itself"),
        }
    }
}
