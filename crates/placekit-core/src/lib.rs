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
