# Experimental interchange draft 0.1

This document describes concepts for future interoperability between independent
scientific tools. It is not a stable schema, does not imply that another project
already imports OperandoMerge output, and may change incompatibly.

## Concepts

| Concept | Draft fields | Rule |
|---|---|---|
| Dataset | `dataset_id`, `title`, `experiment` | One logical source or merged result |
| Channel | `name`, `quantity`, `unit`, `semantics` | Semantics are continuous, stepwise, event, or discrete sample |
| Time | `canonical_column`, `unit`, `origin`, `timezone` | Canonical duration is seconds; absolute origin is preserved separately |
| Experiment metadata | operator-provided key/value records | No scientific meaning is inferred from an unknown key |
| Source information | file name, media type, checksum, adapter | Source identity must survive conversion |
| Provenance | source column/row/time, offset, delay, method | Derived values reference all contributing source rows |
| QC issue | severity, code, dataset, channel, row, message | QC is separate from the numeric value table |

Units in this draft are declared strings. OperandoMerge 0.1.x does not perform
general unit conversion, so consumers must not assume dimensional equivalence
merely because two channels share a quantity name.

## Illustrative envelope

```json
{
  "schema_id": "operandomerge-interchange-draft-0.1",
  "dataset": {
    "dataset_id": "synthetic-operando-001",
    "title": "Five-instrument synthetic operando experiment"
  },
  "time": {
    "canonical_column": "experiment_time_s",
    "unit": "s",
    "origin": "2026-01-01T12:00:00Z",
    "timezone": "UTC"
  },
  "channels": [
    {
      "name": "gc_co2_mol_pct",
      "quantity": "amount_fraction",
      "unit": "mol%",
      "semantics": "discrete_sample"
    }
  ],
  "source": {
    "file": "gas_chromatograph.csv",
    "media_type": "text/csv",
    "checksum": "sha256:<value>",
    "adapter": "operandomerge.csv"
  },
  "provenance_table": "provenance.csv",
  "qc_table": "qc.csv"
}
```

Before this draft can stabilize, it needs independent consumer implementations,
unit vocabulary decisions, timezone/clock uncertainty fields, checksum rules,
and roundtrip fixtures. Until then, the existing Excel/CSV/config exports are the
only supported OperandoMerge artifacts.

