# Contributing

Thank you for helping make multi-instrument timelines reproducible.

## Before opening an issue

Use the dataset-compatibility or scientific-result form when applicable. Never upload
unpublished, confidential, proprietary, licensed, identifying, or sensitive research
data to a public issue. Prefer a minimal synthetic reproducer or sanitized time/header
schema.

## Development checks

Please open an issue before changing scientific definitions. Keep CLI/GUI calculations
in `MergeService`/core and run:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
mypy src
pytest
python -m build
```

Use focused commits. Do not weaken tolerances merely to pass a noisy test. Report
whether a failure is an implementation, test, scientific-definition, unit,
data-model, or environment problem.

## Scientific changes

A change to timestamp parsing, timezone handling, alignment direction, delay sign,
timeline construction, interpolation, stepwise hold, or discrete/event semantics must
state:

- the exact transformation/equation, clock basis, units, assumptions, and ambiguity;
- a primary reference or public-data DOI when relevant;
- whether existing timestamps or merged values change and why;
- a hand-checkable or legally usable regression covering normal, boundary, invalid,
  and sparse/off-grid inputs; and
- the impact on provenance, QC, API, CLI, GUI preview, and exports.

`pytest` passing alone does not establish scientific correctness. Preserve raw values;
never silently invent timezone, measurements, offsets, or interpolation. Public-data-
derived fixtures must record source, license, checksum, and reduction method. Never
commit credentials, internal paths, or unlicensed files.

The DGX CI jobs deliberately skip fork pull requests. Maintainers must review external
changes before reproducing them on a same-repository branch; do not weaken that boundary.
