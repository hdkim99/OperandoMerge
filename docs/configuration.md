# Configuration reference

The top-level JSON object contains `datasets` and `merge`. Paths are resolved
relative to the configuration file. Every dataset requires a unique name, time
column, time representation, and at least one channel.

Time representations are `absolute`, `injection_timestamp`, `elapsed_seconds`,
`elapsed_minutes`, and `instrument_local_time`. Alignment methods are `absolute`,
`elapsed`, `manual_offset`, and `reference_event`. The method documents intent;
`manual_offset_s` can be used with any method. Reference-event alignment also
requires `source_event_time_s` and `target_event_time_s`.

Positive delay components are seconds and must be non-negative. They are summed
and subtracted from reported time. Negative clock corrections belong in
`manual_offset_s`, not in a delay field.

Channel data types are `continuous`, `stepwise`, `event`, and `discrete_sample`.
The optional `output_name` overrides the default `<dataset>__<source-column>`.

The merge timeline is either `union` (all measured canonical times) or
`reference` (only times from `reference_dataset`). On a reference timeline,
discrete/event points not exactly present on that timeline intentionally remain
absent; OperandoMerge will not invent them by interpolation.

`experiment_origin` is an optional ISO-8601 absolute timestamp. Set it when an
absolute clock must be tied to a known experiment start (including starts before
the first instrument record). If omitted, the earliest absolute/injection record
is used as zero and that chosen origin is recorded in metadata.
