# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/) and
the project uses [Semantic Versioning](https://semver.org/).

## [0.1.1] - Unreleased

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
