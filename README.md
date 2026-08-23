# OperandoMerge

> Heterogeneous instruments. One reproducible experiment timeline.

[![CI](https://github.com/hdkim99/OperandoMerge/actions/workflows/ci.yml/badge.svg)](https://github.com/hdkim99/OperandoMerge/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

OperandoMerge aligns reactor loggers, MFCs, high-frequency MS, sparse GC, XRD,
Raman, FTIR, and other CSV/XLSX logs without hiding where values came from. It
uses channel semantics to interpolate continuous measurements, hold stepwise
setpoints causally, and keep event/discrete samples strictly discrete.

![Actual OperandoMerge before-and-after showcase](https://raw.githubusercontent.com/hdkim99/OperandoMerge/main/docs/images/showcase-before-after.png)

The figure is generated from the repository's real five-instrument synthetic
workflow. Purple GC values exist only at 120, 300, and 480 s: the other 298
canonical rows remain missing rather than receiving invented chromatograms.

## Install

Python 3.10 or newer is required. PyPI publication is prepared but is not yet
available, so install from the public source repository:

```bash
python -m pip install "operandomerge @ git+https://github.com/hdkim99/OperandoMerge.git"
```

For development:

```bash
git clone https://github.com/hdkim99/OperandoMerge.git
cd OperandoMerge
python -m pip install -e '.[dev]'
```

## 30-second showcase

```bash
mkdir -p showcase-output

operandomerge inspect examples/showcase/reactor_logger.csv

operandomerge merge examples/showcase/config.json \
  --excel showcase-output/operandomerge-showcase.xlsx \
  --plot showcase-output/alignment-cli.png
```

Expected CLI summary:

```text
Merged 5 dataset(s), 301 timeline row(s); QC: 0 error(s), 0 warning(s)
```

The Excel report contains complete `merged`, `metadata`, `provenance`, `qc`, and
`configuration` sheets. To regenerate the source CSVs and showcase figures from
their deterministic equations:

```bash
python examples/showcase/generate_showcase.py --output-dir showcase-output
```

Launch the same workflow through the desktop UI with:

```bash
operandomerge-gui
```

Python's Tk bindings are included with python.org installers. Some distro or
Homebrew Python builds require their matching optional Tk package, such as
`python3-tk` on Debian/Ubuntu.

## What is being aligned?

The showcase represents one 600 s catalyst experiment with deliberately
different clocks and sampling intervals:

| Instrument | Raw sampling | Alignment evidence | Result semantics |
|---|---:|---|---|
| Reactor logger | 10 s | absolute UTC experiment origin | temperature/pressure, continuous |
| MFC controller | 20 s | local event at 100 s = experiment event at 120 s | H₂/Ar flow, stepwise |
| MS | 2 s | known 8 s transport delay | m/z 44/28, continuous |
| GC | three injections | 12 s sampling + 18 s analysis delay | compositions, discrete samples |
| XRD | 60 s | −5 s clock offset + 15 s analysis delay | phase stepwise; lattice discrete |

The raw clocks and applied corrections remain in metadata/provenance. See the
[showcase definition](examples/showcase/README.md) for hand-checkable invariants.

## Scientific rules

The canonical coordinate is `experiment_time_s`:

```text
experiment_time_s = source_time_s + alignment_offset_s - total_delay_s
total_delay_s = manual + sampling + transport + dead_volume + analysis
```

A positive delay means a reported value corresponds to an earlier physical event,
so it is subtracted. Reference-event alignment uses
`target_event_time_s - source_event_time_s`. Absolute timestamps use an explicit
ISO-8601 experiment origin when provided; otherwise the earliest absolute record
becomes zero.

| Channel semantic | Available policy | Scientific constraint |
|---|---|---|
| `continuous` | linear, nearest, none | bounded by measured range; no extrapolation |
| `stepwise` | previous, none | causal hold; never takes a future setpoint |
| `event` | exact timestamp only | never interpolated |
| `discrete_sample` | exact timestamp only | never interpolated |

For every emitted value, provenance identifies the source file, column, row,
original timestamp, offset, delay, and interpolation method. Linear values retain
both bracketing source rows/timestamps.

## GUI and Python API

The GUI workflow is: add files → map clocks/channels → assign channel semantics →
enter offsets/delays/events → choose the timeline → preview → inspect values/QC →
export. Controls are converted to the same configuration models used by the CLI;
the GUI contains no independent scientific formulas.

```python
from pathlib import Path

from operandomerge.config import load_config
from operandomerge.export import export_excel
from operandomerge.service import MergeService

datasets, policy = load_config(Path("examples/showcase/config.json"))
result = MergeService().run(datasets, policy)
export_excel(result, Path("operandomerge-showcase.xlsx"))
```

## Supported, experimental, planned

Supported in 0.1.1:

- multiple CSV/XLSX inputs and one selected worksheet per dataset;
- absolute/injection timestamps, elapsed seconds/minutes, and midnight-wrapping
  instrument-local clocks;
- absolute, elapsed, manual-offset, and reference-event alignment;
- explicit manual/sampling/transport/dead-volume/analysis delays;
- union or named-reference timeline, type-aware merging, QC, provenance, figures,
  CSV bundle, Excel, CLI, Tk GUI, and public Python API; and
- Python 3.10+ packaging with scientific/unit/integration/showcase regressions.

Experimental:

- automatic GUI time-column guesses, which must be reviewed;
- robust-MAD possible-outlier warnings; and
- the [interchange draft](docs/interchange-draft.md), which documents concepts
  but is not a stable cross-project contract.

Planned, not implemented:

- cross-correlation alignment. It will not be added until candidate offsets have
  quantitative confidence, multi-channel agreement, a visual approval step, and
  complete provenance;
- vendor-native binary adapters;
- automatic dead-volume calculation from apparatus geometry; and
- configurable regular target grids.

## Assumptions and limitations

- OperandoMerge cannot prove that two clock events represent the same physical
  event. Users must justify every offset and delay.
- Signal units are preserved as source metadata/names but are not converted or
  dimensionally validated in this release.
- Numeric channels are required for resampling. Categorical phase labels should be
  encoded as documented numeric states or retained outside the merged value table.
- On a named reference timeline, off-grid event/discrete measurements remain
  absent rather than being snapped or interpolated.
- Duplicate times are reported by QC; numeric merging deterministically uses the
  final row at that time while raw files remain untouched.
- GUI tables preview up to 500 rows; exports always contain the complete result.
- Synthetic curves demonstrate synchronization behavior, not validated reactor
  kinetics, mass balances, or diffraction physics.

Validation details are in [scientific validation](docs/scientific-validation.md),
and every JSON setting is described in the
[configuration reference](docs/configuration.md).

## Related tools

These are independent repositories. Direct interoperability is planned, not
currently claimed:

- [Ordifile](https://github.com/hdkim99/ordifile) — chromatographic file conversion
- [ReactorCheck](https://github.com/hdkim99/ReactorCheck) — catalytic reactor calculation and QC
- [TPxLab](https://github.com/hdkim99/TPxLab) — temperature-programmed characterization analysis

## Development and citation

```bash
ruff check .
mypy src
pytest
python -m build
```

Contributions are welcome under [CONTRIBUTING.md](CONTRIBUTING.md). Cite the
software using [CITATION.cff](CITATION.cff). The project is MIT-licensed; the
[dependency license review](docs/dependency-licenses.md) records compatibility.
