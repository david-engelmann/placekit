//! `placekit-core`: a dependency-light async Rust client for the
//! Google Places API (New).
//!
//! This crate contains all protocol logic (request building, field masks,
//! typed errors, response decoding) with no Python dependency, so it can be
//! tested and reused on its own. The `placekit` Python package is a thin
//! PyO3 binding over it.

pub mod client;
pub mod errors;
pub mod mask;
pub mod models;

pub use client::{Client, ClientBuilder, DEFAULT_BASE_URL};
pub use errors::Error;
pub use mask::FieldMask;

/// Builders shared by the crate's test modules, so a shape two
/// batteries depend on is written once and cannot drift between
/// them.
#[cfg(test)]
pub(crate) mod test_support {
    /// Nested arrays of the given depth around a scalar leaf.
    pub(crate) fn nested_arrays(depth: usize) -> String {
        let mut body = String::new();
        for _ in 0..depth {
            body.push('[');
        }
        body.push('1');
        for _ in 0..depth {
            body.push(']');
        }
        body
    }
}
