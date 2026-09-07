# Tutorial: Running the DT Freshness-Aware NDN Experiment

This tutorial walks through the complete workflow from an existing ns-3/ndnSIM installation to validated experiment results and publication figures.

## 1. What the experiment studies

A Digital Twin producer periodically samples a changing physical state. Consumers request the DT state through either IP/UDP or NDN. With NDN, an MEC Content Store can serve a cached DT object without contacting the producer.

The central question is:

> Can the network reuse cached DT state only when that state is still fresh enough for the requesting application?

The proposed mechanism uses a request-specific freshness budget `F_max` and checks the **expected state age at delivery** rather than relying only on native NDN cache residence freshness.

## 2. Mechanisms

### A — IP/UDP - No Cache

Every request goes to the DT source. It is the non-NDN source-retrieval reference.

### B — NDN - No Cache

NDN forwarding is used, but the MEC Content Store size is zero. It isolates NDN forwarding overhead from caching effects.

### C — NDN - Native Cache

Native NFD caching is enabled. The producer assigns a single `FreshnessPeriod`, and consumers use `MustBeFresh`.

This freshness mechanism is global to the produced Data and does not express different application freshness budgets for the same DT state.

### D — NDN - Freshness-Aware Cache

The proposed mechanism accepts cached DT Data only when:

```text
cached_state_age + downstream_delivery_guard <= F_max
```

If the cached copy is too old, the hit is converted to the normal NFD miss path and the state is retrieved from the source.

## 3. Prerequisites

You need:

- Linux;
- a working ns-3 + ndnSIM source tree;
- `waf` at the ns-3 root;
- Python 3;
- Python packages listed in `requirements.txt`.

Set the ns-3 path once:

```bash
export NS3_ROOT=/home/fablab/Desktop/ndnSIM/ns-3
```

Change this path to your own installation.

## 4. Check compatibility

From the cloned repository:

```bash
bash scripts/check_environment.sh "$NS3_ROOT"
```

A compatible environment should report the ns-3 root, the ndnSIM Git revision, the NFD Content Store pipeline, and finish with:

```text
Environment check passed.
```

The experiment was validated against ndnSIM commit:

```text
90d5039
```

If your NFD API is substantially different, the automatic Forwarder patch intentionally aborts rather than modifying an unknown source layout.

## 5. Install the experiment into ns-3

```bash
bash scripts/install_into_ns3.sh "$NS3_ROOT"
```

This copies:

```text
scratch/dt-freshness-study.cc  -> <NS3_ROOT>/scratch/
dt-study-src/                  -> <NS3_ROOT>/dt-study-src/
scripts/*                      -> <NS3_ROOT>/dt-study-tools/
```

The helper directory is deliberately outside `scratch/`. In this ns-3/waf generation, a direct helper directory under `scratch/` can be treated as a separate scratch executable and produce a linker error due to a missing `main()`.

## 6. Apply the freshness-aware cache instrumentation

Arm D needs access to the NFD Content Store hit/miss path.

Run:

```bash
python3 scripts/apply_freshness_patch.py "$NS3_ROOT"
```

The patcher:

1. finds `src/ndnSIM/NFD/daemon/fw/forwarder.cpp`;
2. detects the supported Content Store API ordering;
3. creates `forwarder.cpp.dtstudy.bak` once;
4. adds the Arm-D freshness check and cache-event logging.

A successful run prints the detected NFD API and the patched file path.

## 7. Build

```bash
cd "$NS3_ROOT"
./waf
```

The simulation program should now be discoverable as:

```text
dt-freshness-study
```

The scratch file extension is `.cc`, not `.cpp`, because this waf setup discovers scratch programs using the `.cc` convention.

## 8. Run the smoke test first

```bash
bash dt-study-tools/run_smoke_tests.sh "$NS3_ROOT"
```

The script executes A, B, C, and D for a short run, analyzes the CSVs, and verifies paired request traces.

The required final line is:

```text
Smoke validation PASS
```

The smoke test also checks that:

- offered request IDs match across mechanisms;
- request send timestamps match across mechanisms;
- there are no unexpected timeouts.

If the smoke test fails, do not start the full experiment.

## 9. Run one configuration manually

A useful first example is E1 with Arm D and `F_max=100 ms`:

```bash
cd "$NS3_ROOT"
./waf --run="dt-freshness-study \
  --arm=D \
  --experiment=e1 \
  --run=1 \
  --simulationTime=20 \
  --warmupTime=2 \
  --updatePeriodMs=10 \
  --requestRateHz=10 \
  --requestJitterMs=5 \
  --requestTimeoutMs=80 \
  --freshnessDeliveryGuardMs=2 \
  --payloadBytes=512 \
  --cacheSize=1 \
  --fmaxMs=100 \
  --nativeFreshnessMs=500 \
  --outputRoot=tutorial-results"
```

This short run is useful for learning the files before launching the full study.

## 10. Understand the important command-line parameters

| Parameter | Meaning |
|---|---|
| `--arm` | A, B, C, or D |
| `--experiment` | `smoke`, `e1`, or `e4` |
| `--run` | run/seed identifier |
| `--simulationTime` | total simulation duration in seconds |
| `--warmupTime` | time excluded before measurement begins |
| `--updatePeriodMs` | producer DT state sampling period |
| `--requestRateHz` | consumer request rate |
| `--requestJitterMs` | random request-time perturbation |
| `--requestTimeoutMs` | application request timeout |
| `--fmaxMs` | E1 application freshness budget |
| `--strictFmaxMs` | E4 strict consumer freshness budget |
| `--relaxedFmaxMs` | E4 relaxed consumer freshness budget |
| `--nativeFreshnessMs` | native producer `FreshnessPeriod` for Arm C |
| `--cacheSize` | MEC Content Store capacity in packets |
| `--freshnessDeliveryGuardMs` | estimated downstream delay added to cached state age |
| `--payloadBytes` | approximate DT Data payload size |
| `--outputRoot` | directory containing the run result folders |

## 11. Run the complete E1 + E4 matrix

From the ns-3 root:

```bash
python3 dt-study-tools/run_paper_experiments.py \
  --ns3-root "$NS3_ROOT" \
  --results-root paper-results-v2 \
  --runs 20 \
  --simulation-time 60 \
  --warmup-time 5 \
  --request-rate-hz 10 \
  --update-period-ms 10 \
  --request-jitter-ms 5 \
  --payload-bytes 512 \
  --cache-size 1
```

The default matrix contains 320 configurations.

### E1 — Freshness-efficiency sweep

Reference mechanisms:

```text
A, B, C
```

Proposed mechanism:

```text
F_max = 10, 20, 50, 100, 200, 500, 1000, 2000 ms
```

### E4 — Heterogeneous application freshness

Two consumers use the same DT object and shared cache behavior:

```text
strict consumer : F_max = 20 ms
relaxed consumer: F_max = 500 ms
```

Compared configurations:

```text
A
B
C with FreshnessPeriod = 20 ms
C with FreshnessPeriod = 500 ms
D with per-consumer F_max = 20/500 ms
```

## 12. Resume or re-run

The experiment runner checks for completed result directories and skips them.

To see what would run without executing simulations:

```bash
python3 dt-study-tools/run_paper_experiments.py \
  --ns3-root "$NS3_ROOT" \
  --results-root paper-results-v2 \
  --runs 20 \
  --dry-run
```

To force re-execution:

```bash
python3 dt-study-tools/run_paper_experiments.py \
  --ns3-root "$NS3_ROOT" \
  --results-root paper-results-v2 \
  --runs 20 \
  --force
```

## 13. Analyze an existing result directory

```bash
python3 dt-study-tools/analyze_results.py paper-results-v2
```

The analyzer creates aggregate and request-level files while preserving the complete AoI and latency samples.

Two checks are especially important:

### Pairing validation

```text
pairing-validation.csv
```

For every paired run, verify:

```text
exact_request_id_match = 1
exact_send_trace_match = 1
```

### Timeout validation

Inspect:

```text
summary.csv
all-timeouts.csv
```

The standard experiment is designed so that the previous request has completed or timed out before the minimum next request interval. This prevents a slow mechanism from reducing its own offered workload.

## 14. Generate publication figures

```bash
python3 dt-study-tools/make_paper_results.py \
  --results-root "$NS3_ROOT/paper-results-v2" \
  --skip-analyzer
```

The most useful E1 figures include:

```text
fig-e1-freshness-violation
fig-e1-backhaul
fig-e1-aoi-ecdf-main
fig-e1-mean-latency
fig-e1-proposed-cache-source-ratio
fig-e1-latency-backhaul-savings
fig-e1-policy-latency-fmax500
```

Bar figures use hatching patterns so the policies remain distinguishable in grayscale.

## 15. How to interpret the main metrics

### Age of Information

For a delivered DT state generated at time `t_generation` and received at `t_receive`:

```text
AoI = t_receive - t_generation
```

Lower AoI means fresher information.

### Freshness violation ratio

A request violates freshness when:

```text
AoI > F_max
```

The ratio is computed over satisfied requests.

### Retrieval latency

```text
latency = receive_time - request_send_time
```

The experiment typically produces two dominant paths:

- a low-latency MEC cache-served path;
- a higher-latency DT-source retrieval path.

For this reason, the repository also reports mean latency and cache/source serving ratio instead of relying only on latency ECDFs.

### Backhaul bytes per offered request

```text
backhaul bytes / number of offered requests
```

Using offered requests avoids rewarding a mechanism merely because it satisfied fewer requests.

### Cache-hit ratio

The analyzer uses exact NFD cache-event instrumentation rather than inferring cache hits from latency.

## 16. Why the 10 ms freshness point may be infeasible

The DT update period and source/network delay impose a physical lower bound on the achievable state age. If `F_max` is below that bound, even a no-cache source retrieval can violate the requested freshness constraint.

Therefore, a violation at an extremely strict budget should be interpreted as an **infeasible freshness request**, not automatically as a cache-policy failure.

## 17. Revert the NFD patch

```bash
python3 scripts/apply_freshness_patch.py "$NS3_ROOT" --revert
cd "$NS3_ROOT"
./waf
```

## 18. Recommended reproducibility checklist

Before publishing a result set:

- [ ] Environment checker passes.
- [ ] Smoke validation passes.
- [ ] Full matrix completes.
- [ ] `analysis-data-quality.csv` reports PASS.
- [ ] Paired request IDs match.
- [ ] Paired request send traces match.
- [ ] No unexpected timeout imbalance exists.
- [ ] `paper-experiment-config.json` is archived with the results.
- [ ] ndnSIM/NFD version information is recorded.
- [ ] Figures are generated from the same archived result directory.
