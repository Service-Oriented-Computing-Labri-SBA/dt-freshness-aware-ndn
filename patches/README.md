# Arm-D NFD Forwarder instrumentation — v0.3.0

The study instruments the real NFD Content Store hit/miss path instead of relying on the legacy cache tracer.

For Arm D, a cached DT state is accepted only when:

```text
cached_state_age + downstream_delivery_guard <= F_max
```

The patch also writes exact `HIT`, `MISS`, and `STALE_REJECT` events to `cache-events.csv`, including `cached_state_age_ms`, `delivery_guard_ms`, and `expected_arrival_age_ms`.

The simulation-only nonce carrier preserves a common content name across strict and relaxed consumers; it is not proposed as a production NDN wire format.
