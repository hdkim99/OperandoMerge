# Public-data validation sources

This register separates public research data from the synthetic examples bundled
with OperandoMerge. Public archives are never committed to this repository. The
machine-checkable metadata are in
[`validation/public-data-manifest.json`](../validation/public-data-manifest.json),
and access was last checked on **2026-08-23**.

## License and reuse rule

The dataset license, not the related article license, controls reuse of the data.
Both selected Zenodo datasets are licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), which permits sharing
and adaptation when appropriate credit, a license link, and an indication of
changes are provided. Related articles have different licenses and are recorded
separately below. This register is a provenance record, not legal advice.

## OM-PUB-001 — primary same-run GC/MS alignment

**Complete dataset citation.** Becker, Matthias; Baidun, Margareth; Landuyt,
Annelies; Kierzkowska, Agnieszka; Donat, Felix; Kolganov, Alexander; Pidko,
Evgeny; Abdala, Paula; Fedorov, Alexey; and Müller, Christoph (2026), “Dataset
for: Dopant-Controlled Oxygen Vacancy Dynamics Define CO2-to-Methanol Catalysis
on In2O3,” Zenodo, version DOI
[10.5281/zenodo.21884075](https://doi.org/10.5281/zenodo.21884075), concept DOI
[10.5281/zenodo.19450659](https://doi.org/10.5281/zenodo.19450659). Accessed
2026-08-23.

The related article is Becker et al., “Dopant-controlled oxygen vacancy dynamics
define CO2-to-methanol catalysis on In2O3,” *Nature Communications* (2026), DOI
[10.1038/s41467-026-72876-w](https://doi.org/10.1038/s41467-026-72876-w).
Zenodo identifies the record as supplementary to that article.

- Dataset license: CC BY 4.0.
- Article license in Crossref metadata at access time: CC BY-NC-ND 4.0.
- Validation level: **primary**, real same-run heterogeneous GC/MS alignment.
- Data-use decision: checksum-pinned, opt-in validation is permitted with
  attribution. OperandoMerge does not redistribute the public archive.
- Metadata note: the deposited `README.rtf` names the earlier version DOI
  `10.5281/zenodo.19450660`; validation uses and cites the downloaded version DOI
  `10.5281/zenodo.21884075`.

### Source files and members

| Archive/member | Bytes | SHA-256 or role |
|---|---:|---|
| `04_Figure_4_a_catalysis_operando.zip` | 6,132,151 | `bcadc5efc35229e1920c04500ca3325164137ff2c677b2487c2b392ba439810f` |
| `…/In2O3_5Sn_GC_data.txt` | 25,948 | Chromeleon component tables |
| `…/In2O3_5Sn_MS_data_export.csv` | 1,169,428 | text export of the corresponding MS run |
| `…/In2O3_5Zr_GC_data.txt` | 100,444 | Chromeleon component tables |
| `…/In2O3_5Zr_MS_data_export.csv` | 4,059,570 | text export of the corresponding MS run |
| `…/In2O3_5Sn_MS_data.qmp` | 4,075,520 | vendor original; unsupported and not extracted |
| `…/In2O3_5Zr_MS_data.qmp` | 9,035,776 | vendor original; unsupported and not extracted |
| `08_Figure_5_d_e_f_g_TPR.zip` | 4,401,662 | `f1489430b9cf1f664f64ca27a117e26cadb597e6d250ff0ec4c82758578886e8` |
| `…/In2O3_5Zr_TPR_5H2Ar01CO2.csv` | 2,953,645 | combined TCD/temperature/MS QC case |

The archive-level size and SHA-256 are checked before any member is opened. Only
the named members are copied into an operating-system temporary directory.

### Observed clocks and sampling

| Run/channel | Rows or samples | Local range | Observed cadence |
|---|---:|---|---|
| 5Sn GC | 64 injections | 2024-01-31 16:32 to 2024-02-01 00:12 | min/median/max 420/420/480 s |
| 5Sn MS | 7,639 rows | 2024-01-31 15:25:06 to 2024-02-01 00:23:49 | 4/4/5 s |
| 5Zr GC | 255 injections | 2024-02-01 19:47 to 2024-02-03 02:38 | 420/420/480 s |
| 5Zr MS | 26,552 rows | 2024-02-01 19:28:58 to 2024-02-03 02:41:24 | 4/4/5 s |

The published MS `timestamp - hours since RX start` identity gives a constant
local experiment origin: `2024-01-31 19:00:00` for 5Sn and
`2024-02-01 22:58:00` for 5Zr. No timezone is deposited. These values therefore
are **local wall clocks, not UTC timestamps**.

Chromeleon uses two explicit representations in the same export:
`%d/%m/%Y %H:%M` and `%d/%b/%Y %H:%M`. The validation preprocessor accepts only
those documented formats and converts them to elapsed seconds relative to the
independently checked local RX origin. It retains the unzoned ISO local text but
never passes it to the `absolute` parser.

### Executed validation result

The opt-in script was run against both checksum-verified archives on 2026-08-23.

| Assertion | 5Sn | 5Zr |
|---|---:|---:|
| Union timeline rows | 7,689 | 26,748 |
| GC values at exact injection times | 64 | 255 |
| GC values between injections | all NaN | all NaN |
| GC provenance rows, method | 64, `original` | 255, `original` |
| API/CLI/GUI-controller results | identical | identical |
| Core QC errors | 0 | 0 |
| Core QC warnings | 7 | 7 |

Warnings are expected missing-component amounts in the raw GC tables; MS robust
outlier notices are informational. API Excel, CLI CSV/plot, and GUI-controller
Excel exports were read back. The script joins core `source_row` provenance to
the derived rows and preserves `source_archive`, `source_member`, `source_line`,
and `injection_id` in the validation exports.

### TPR classification

The Figure 5 TPR table is real research data but is already a combined table, so
it is **not** primary multi-file alignment evidence. It is a secondary sparse and
duplicate-timestamp QC oracle:

- 16,665 table rows;
- 8,184 populated MS rows and 4,089 unique MS timestamps;
- 4,095 zero-time transitions, no decreasing transition;
- positive MS cadence min/median/max 4.072998/4.074/4.081 s; and
- all 8,184 rows participating in duplicate timestamps are reported by existing
  `duplicate_timestamp` QC and survive the Excel QC export.

Equal adjacent timestamps do not trigger `non_monotonic_time`, because the input
is nondecreasing. Duplicate QC is the applicable classification.

## OM-PUB-002 — conditional event alignment

**Complete dataset citation.** Bachmann, Lydia J.; Dwivedi, Jagrati; Lapkin,
Dmitry; Wang, Bihan; Schober, Jan-Christian; Hinsley, Gerard N.; Bernart, Sarah;
Ngoi, Kuan Hoon; Rysov, Rustam; Dangwal Pandey, Arti; Keller, Thomas F.;
Vartaniants, Ivan; and Stierle, Andreas (2025), “Raw data for manuscript Lydia
J. Bachmann et al., In situ X-ray imaging of segregation and mixing in PtPd
core-shell nanoparticles under methane oxidation conditions,” Zenodo, DOI
[10.5281/zenodo.17642484](https://doi.org/10.5281/zenodo.17642484). Accessed
2026-08-23.

The title and authors correspond to Bachmann et al., *Nanoscale* (2026), DOI
[10.1039/D5NR05321H](https://doi.org/10.1039/D5NR05321H). The Zenodo record does
not itself provide a formal related-identifier link, so the association is
recorded as a title/author match rather than a repository-declared relation.

- Dataset license: CC BY 4.0.
- Article license in Crossref metadata at access time: CC BY-NC 3.0.
- Validation level: **conditional**, event alignment only.
- Data-use decision: suitable for a future lightweight MS/event-log audit; not
  selected for the current primary regression.

| Archive/member group | Bytes | SHA-256 or observation |
|---|---:|---|
| `Masspec_data.zip` | 33,943,813 | `252c5830042a79aa45d4f1dfff2c02969d3eff9b74cbebc8324b134e67058f0e` |
| Uncompressed MS archive | 110,415,388 | 6,097 exported TXT scans plus RGA/ANA originals |
| `OverviewChanges.zip` | 3,158 | `e4c79ccb03814f4227b2d25f0810d43327f8a291a0af7689197c05bffc849b85` |
| `EBL2021_BCDI.txt` | 601 | date plus minute-resolution BCDI start events |
| `EBL2021_gases.txt` | 1,541 | gas-change events |
| `EBL2021_heating.txt` | 1,037 | heating/cooling events |
| `P10_ID01#4_BCDI.txt` | 414 | date plus minute-resolution BCDI start events |
| `P10_ID01#4_gases.txt` | 434 | gas-change events |
| `P10_ID01#4_heating.txt` | 640 | heating/cooling events |
| Two raw BCDI archives | 33,848,760,107 | not downloaded during the audit |

Each exported MS scan contains a naive local datetime, 641 points from 1–65 amu,
and pressure in Torr. Four principal inspected groups sampled at approximately
29 s or 60 s. The event logs have only minute precision, no timezone, and some
comments explicitly describe estimated or unclear times. They are useful for QC
and reference-event demonstrations, but not an exact offset oracle. Numerical
diffraction validation would also require the approximately 33.85 GB raw BCDI
archives.

## Reproducing OM-PUB-001 without vendoring data

Install the checkout, then either point to previously downloaded archives or
explicitly opt into the two Zenodo downloads. The output must be a new or empty
directory outside the repository.

```bash
python -m pip install -e .
python validation/validate_public_data.py \
  --source-dir /path/to/checksum-pinned-zips \
  --output-dir /tmp/operandomerge-public-validation
```

Or:

```bash
python validation/validate_public_data.py \
  --download \
  --output-dir /tmp/operandomerge-public-validation
```

The workflow is notebook-free and performs:

1. archive size/SHA-256 validation;
2. temporary extraction of named members only;
3. deterministic GC component parsing and MS elapsed-clock cross-checking;
4. distinct derived GC and MS CSV creation outside the repository;
5. API merge and Excel/plot export;
6. real CLI merge and CSV/plot export;
7. real `GuiController` load, merge, and Excel export;
8. cross-interface result comparison, discrete GC assertions, provenance join,
   TPR QC, and export readback; and
9. a machine-readable `validation-report.json`.

With a functional Tk display (or `xvfb-run`), the real widget path can be run
against one generated public-data configuration and its processed sources:

```bash
python tests/gui_widget_smoke.py \
  /tmp/operandomerge-public-validation/5Sn/config.json \
  /tmp/operandomerge-public-validation/5Sn/gui-widget-report.xlsx
```

TXT, ZIP, QMP, RGA, ANA, XANES, and XRD adapters are deliberately not added to
the OperandoMerge core by this validation workflow.

## Failure register and unsupported claims

| ID | Finding | Status/handling |
|---|---|---|
| OM-PUB-F01 | `absolute` previously passed naive `2024-01-31 15:25:06` to `utc=True`, silently inventing UTC | Resolved: absolute/injection values without an offset now raise an actionable error; timezone-aware ISO remains supported |
| OM-PUB-F02 | GC dates mix numeric month and English month abbreviation | Resolved in the opt-in preprocessor with two explicit, locale-independent formats; no inference |
| OM-PUB-F03 | Public GC is TXT inside ZIP and QMP is vendor-native | Unsupported in core; temporary validation preprocessing only |
| OM-PUB-F04 | Figure 5 TPR repeats MS scans on adjacent 1 s rows | Existing duplicate QC detects all affected rows; combined table is not presented as multi-file evidence |
| OM-PUB-F05 | XANES/XRD series provide spectra or step labels but no scan-level timestamp | Unsupported for timeline alignment; no offset is inferred |
| OM-PUB-F06 | Source timezone and physical transport delay are not deposited | Local elapsed alignment only; no UTC or delay claim |
| OM-PUB-F07 | OM-PUB-002 BCDI raw volumes are approximately 33.85 GB and event logs have minute/estimated timing | Conditional candidate only |

## Search exclusions

- Zenodo 21819240: genuine Raman–Mössbauer study, but OPJU/RAR/PPTX assets and
  no raw shared MS timeline.
- Zenodo 17063731: XAS-only source.
- Zenodo 7072918: Raman and ToF-SIMS are separate characterization workflows.
- Zenodo 3786440: DRIFTS/GC study with article and supplementary PDFs but no raw
  machine-readable shared timeline.
- Dryad 10.5061/dryad.kg76k5b: separate aggregate XRD/GHSV/TPD experiments, not
  one heterogeneous time-resolved run.
- Figshare 31955846: coupled operando XAS/XRD/MS study, but the record exposes a
  supplementary PDF rather than raw shared-clock data.
- Zenodo 3514967 and 6560384: genuine battery/photoelectrochemistry fallbacks,
  but weaker catalyst-domain fit and substantially larger modality data.
- OSF and GitHub searches found no stronger candidate with both a reusable
  license and same-run machine-readable clocks.
