# Result Files

Each simulation directory contains raw run-level files. The analyzer also creates aggregate files at the result-root level.

## Per-run files

### `offered-requests.csv`

Every request scheduled/injected by the application. This is the correct denominator for offered-load comparisons.

### `requests.csv`

Satisfied requests, including latency, generation timestamp, AoI, DT state/error, and freshness validity.

### `timeouts.csv`

Requests that were offered but did not complete before the configured timeout.

### `cache-events.csv`

NFD-level cache instrumentation, including events such as:

```text
HIT
MISS
STALE_REJECT
```

For Arm D, the log includes cached state age, delivery guard, and expected arrival age.

### `link-traffic.csv`

Traffic counters used to compute backhaul packets/bytes.

### `config.csv`

Resolved configuration for the run.

## Aggregate files

### `summary.csv`

Per-run/per-consumer descriptive metrics.

### `summary-ci95.csv`

Across-run means and 95% confidence intervals.

### `all-requests.csv`

All satisfied request-level samples across the experiment. Use this for complete AoI and latency distributions.

### `all-offered-requests.csv`

All offered requests across the experiment.

### `all-timeouts.csv`

All timeouts across the experiment.

### `pairing-validation.csv`

Verifies that compared mechanisms receive identical request IDs and request send traces within each paired run.

### `e1-reference-thresholds.csv`

Evaluates A/B/C request samples against the same E1 application freshness thresholds used by D.

### `analysis-data-quality.csv`

High-level data-quality checks for the analysis input.
