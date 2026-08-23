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

