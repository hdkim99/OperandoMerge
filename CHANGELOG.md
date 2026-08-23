# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/) and
the project uses [Semantic Versioning](https://semver.org/).

## [0.1.3] - 2026-08-23

### Added

- Added a checksum-pinned, opt-in public GC/MS and TPR validation workflow that
  keeps all public and derived data outside the repository.

### Fixed

- Reject naive absolute/injection timestamps and experiment origins instead of
  silently interpreting an instrument-local wall clock as UTC.

## [0.1.2] - 2026-08-23

### Fixed

- Made the published PyPI package the primary installation path in the README.
- Corrected the README support status and synchronized package metadata.

## [0.1.1] - 2026-08-23

### Added

- Five-instrument operando showcase with reactor, MFC, MS, GC, and XRD clocks.
- Actual before/after and social-preview images generated from `MergeService` results.
- Showcase regressions for known delays, boundary semantics, provenance, and GC non-interpolation.
- Experimental interchange concepts for channels, units, metadata, provenance, QC, and sources.
- Release-triggered trusted-publishing workflow with isolated build and publish jobs.

### Changed

- Expanded project metadata, README quickstart, assumptions, limitations, and related-tool links.
- CI now regenerates and verifies the full showcase on Python 3.12.

## [0.1.0] - 2026-08-23

### Added

- Lossless time normalization for absolute, injection, elapsed, and local clocks.
- Manual/reference-event alignment and explicit physical delay components.
- Data-type-aware merge without discrete/event interpolation.
- Value provenance, QC, plots, CSV/Excel export, CLI, GUI, and public API.
- Synthetic scientific regression suite and reproducible example workflow.
