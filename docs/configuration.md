# Configuration reference

The top-level JSON object contains `datasets` and `merge`. Paths are resolved
relative to the configuration file. Every dataset requires a unique name, time
column, time representation, and at least one channel.

Time representations are `absolute`, `injection_timestamp`, `elapsed_seconds`,
`elapsed_minutes`, and `instrument_local_time`. Alignment methods are `absolute`,
`elapsed`, `manual_offset`, and `reference_event`. The method documents intent;
`manual_offset_s` can be used with any method. Reference-event alignment also
requires `source_event_time_s` and `target_event_time_s`.

`absolute` and `injection_timestamp` values must contain an explicit ISO-8601
timezone offset, such as `2026-01-01T12:00:00Z` or
`2026-01-01T13:00:00+01:00`. OperandoMerge does not silently interpret a naive
instrument wall clock as UTC. An explicit `experiment_origin` must carry the
same offset information. If instruments share only an unzoned local clock,
map `HH:MM:SS[.sss]` to `instrument_local_time`, or derive an elapsed coordinate
with a documented reference event. Preserve the original wall-clock column as
source metadata; do not add a guessed timezone.

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
