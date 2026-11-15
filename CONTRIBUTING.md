# Contributing to placekit

The development loop and the gate live in the Development section of the [README](README.md). Set up the environment the way that section describes, then run the one gate command before sending a change.

```bash
make check
```

CI runs that command word for word, and a change is ready when it passes locally. Keep changes small, keep the changelog's Unreleased section current for anything a caller can observe, and never include a real Google API key in code, fixtures, or issue reports.
