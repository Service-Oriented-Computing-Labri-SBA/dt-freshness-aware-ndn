# Design notes — v0.3.0

| Code | Full approach name | Cache logic |
|---|---|---|
| A | IP/UDP - No Cache | source retrieval |
| B | NDN - No Cache | NDN forwarding, MEC CS=0 |
| C | NDN - Native Cache | native NFD CS + producer FreshnessPeriod + MustBeFresh |
| D | NDN - Freshness-Aware Cache (Proposed) | request-specific F_max and expected-arrival age |

At 10 requests/s ±5 ms, inter-request time is 95–105 ms. The 80 ms application timeout guarantees the prior request has either completed or timed out before the next scheduled request. Requests are never suppressed by mechanism latency. `pairing-validation.csv` must confirm identical request IDs and send timestamps.

Arm D uses `A_expected = A_cache + G_downstream` and accepts a cached state only if `A_expected <= F_max`. The default guard is 2 ms for the current static MEC1-to-consumer access path. It is logged explicitly and should be replaced by a path-specific estimator when E3 mobility is implemented.

No p95 AoI or p95 latency is used. Full request-level distributions are kept. 95% confidence intervals across independent run-level means may still be reported; that is statistical uncertainty, not a percentile metric.
