# Contributing

Please open an issue before changing scientific definitions. A contribution must
preserve raw values, document clock/delay semantics, include a hand-checkable or
synthetic regression case, and keep CLI/GUI calculations in `MergeService`/core.

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

