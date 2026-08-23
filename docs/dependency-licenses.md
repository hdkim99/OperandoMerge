# Dependency and license review

The v0.1 runtime stack intentionally uses established PyData libraries and the
standard-library Tk GUI. Distribution metadata was inspected on 2026-08-23.

| Dependency | Purpose | Declared license family | Compatibility |
|---|---|---|---|
| NumPy | array/resampling operations | BSD-3-Clause plus bundled permissive notices | MIT-compatible |
| pandas | tabular IO and time handling | BSD-3-Clause | MIT-compatible |
| Matplotlib | alignment figures | PSF/BSD-style plus bundled permissive/font notices | MIT-compatible |
| openpyxl | XLSX IO | MIT | MIT-compatible |
| Hatchling | build backend | MIT | build-time, MIT-compatible |
| pytest | tests | MIT | development-only |
| Ruff | lint/format | MIT | development-only |
| mypy | static typing | MIT | development-only |

No dependency code is copied into this repository. OperandoMerge is distributed
under MIT; downstream wheels retain each dependency's own license materials.
Version ranges are bounded to avoid unreviewed major-version changes.
