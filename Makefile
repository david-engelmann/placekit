# The gate for this repo. A green local run of `make check` is the
# definition of done; CI runs this target word for word (see
# .github/workflows/ci.yml), so there is one gate, not two.
#
# The Python steps need a development venv with the dev extras, which
# carry pytest, mypy and maturin on the one pin pyproject declares:
#   python -m venv .venv && .venv/bin/pip install -e '.[dev]'
# Cargo must be on PATH for the Rust steps.

VENV ?= .venv
PY := $(VENV)/bin/python
MATURIN := $(VENV)/bin/maturin

.PHONY: check
check:
	cargo fmt --check
	cargo clippy --workspace --all-targets --locked -- -D warnings
	cargo test --workspace --locked
	python3 scripts/check_version.py
	python3 scripts/check_no_emdash.py
	$(MATURIN) develop --locked
	$(PY) -m mypy.stubtest placekit
	$(PY) -m pytest
