---
name: Bug report
about: Report something placekit does wrong
title: ""
labels: bug
assignees: ""
---

**placekit version**
The output of `python -c "import placekit; print(placekit.__version__)"`.

**Platform and wheel**
Your operating system and architecture, your Python version, and whether you installed a wheel or built from the source distribution.

**Endpoint**
Which call failed, for example `text_search`, `place_details`, or `place_photo`.

**Field mask**
The `fields` value you passed, or "default" if you passed none.

**Minimal call**
The smallest call that reproduces the problem, with your API key removed. Never paste a real key into an issue.

```python

```

**What happened**
What placekit did, including the exception class and message if it raised.

**What you expected**
What you expected instead.
