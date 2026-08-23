# Scientific validation

The bundled synthetic experiment is deliberately hand-checkable.

- The reactor logger records at 0, 10, 20, and 30 s.
- The MS reports at 2, 12, 22, and 32 s with a 2 s sampling delay. After delay
  correction it must align at exactly 0, 10, 20, and 30 s.
- GC injection timestamps occur at 5 and 25 s after the absolute experiment
  origin with a 5 s analysis delay. They must align at 0 and 20 s.
- GC is `discrete_sample`; its value must remain absent at 10 and 30 s.
- Reactor temperature is continuous; on a union timeline an intermediate source
  time must be linearly interpolated only inside the measured domain.
- Valve state is stepwise and uses a causal previous-value hold.

The test suite independently asserts these expected times and values rather than
comparing the implementation to itself. It also tests known reference-event
offset recovery, local-clock midnight rollover, minute-to-second conversion,
no extrapolation, scaling linearity, duplicate/missing QC, and provenance fields.

Timezone-aware ISO-8601 inputs are normalized to UTC. Naive values in
`absolute` or `injection_timestamp` columns, and naive `experiment_origin`
values, are rejected rather than silently localized to UTC. The regression uses
the unzoned timestamp representation found in the selected public MS data.
Details and the opt-in real-data workflow are in
[public-data validation sources](public-data-sources.md).

## Five-instrument showcase regression

The larger `examples/showcase` workflow adds independent reactor, MFC, MS, GC,
and XRD clocks over 600 s:

- reactor UTC records define the absolute origin and sample every 10 s;
- the MFC source event at local elapsed 100 s is aligned to experiment 120 s,
  producing a known +20 s offset;
- MS values reported at 8–608 s have an 8 s transport delay and must recover
  exactly 0–600 s;
- GC values reported 30 s after physical sampling separate that delay into 12 s
  sampling and 18 s analysis components. The three values must land at 120, 300,
  and 480 s, while 298 other canonical rows stay missing;
- XRD values reported 20 s late combine a −5 s clock offset and 15 s analysis
  delay to recover 0, 60, …, 600 s; and
- the union timeline must contain exactly 301 rows at 2 s intervals with no QC
  issues for the valid synthetic inputs.

Regression tests also confirm causal stepwise holding, no MFC extrapolation before
its first physical record, GC composition sums of 100 mol%, discrete XRD lattice
measurements, left/right source provenance for reactor interpolation, config
roundtrip, physically invalid negative delay rejection, and real CLI Excel/plot
generation. The signal curves are visualization fixtures, not kinetic or
diffraction reference models.
