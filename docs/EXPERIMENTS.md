# Experiment Design

## Shared topology

The static study uses two consumers, three MEC nodes, and one DT producer. The compared mechanisms use the same application workload and link configuration; only the forwarding/cache behavior changes.

The implementation names the nodes:

```text
StrictConsumer -- MEC1 -- MEC2 -- MEC3 -- RelaxedConsumer
                              |
                         Robot27Producer
```

The central evaluation goal is to separate the effect of the network/cache mechanism from the offered workload.

## Digital Twin state

The producer maintains a continuously changing synthetic physical state and samples it periodically. Each produced DT state includes:

- state version;
- generation timestamp;
- state coordinates/value.

The generation timestamp is used to compute absolute state age at delivery.

## Synchronization/freshness model

For native NDN caching, Arm C uses producer `FreshnessPeriod` and consumer `MustBeFresh`.

For Arm D, the relevant quantity is physical-state age:

```text
A(t) = t - t_generation
```

A cached state is accepted using expected-arrival freshness:

```text
A_expected = A_cache + G_downstream
```

and:

```text
A_expected <= F_max
```

The default static downstream delivery guard is 2 ms. It is explicit in the configuration and event logs.

## E1 — Freshness-efficiency sweep

Purpose: quantify how the application freshness tolerance controls cache reuse, AoI, retrieval latency, freshness violations, and backhaul cost.

Proposed `F_max` values:

```text
10, 20, 50, 100, 200, 500, 1000, 2000 ms
```

Arm C uses a native producer freshness period of 500 ms as a fixed-cache reference.

## E4 — Heterogeneous freshness

Purpose: test whether applications with different freshness requirements can share the same DT object/cache behavior without forcing one global freshness threshold.

```text
Strict consumer  : F_max = 20 ms
Relaxed consumer : F_max = 500 ms
```

Arm C is tested twice:

```text
FreshnessPeriod = 20 ms
FreshnessPeriod = 500 ms
```

Arm D carries the request-specific freshness budget while preserving a common content name, allowing the same cached DT object to be evaluated differently for different consumers.

## Fair-load controls

At 10 requests/s with ±5 ms jitter, the inter-request interval is 95–105 ms. The standard request timeout is 80 ms.

This guarantees that a previous request has completed or timed out before the next scheduled request. The application therefore does not suppress future offered requests because one mechanism was slower.

The analyzer validates identical offered request IDs and send timestamps across paired mechanisms.

## Metrics

Primary metrics:

- complete AoI distribution;
- freshness violation ratio;
- mean retrieval latency and complete latency samples;
- DT synchronization error;
- cache-hit ratio;
- valid-cache-hit ratio;
- backhaul bytes per offered request.

The project intentionally avoids p95 AoI and p95 latency. Complete samples are retained, while 95% confidence intervals are used across independent runs to report statistical uncertainty.
