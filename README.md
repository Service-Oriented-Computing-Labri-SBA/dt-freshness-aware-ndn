# Freshness-Aware Digital Twin Caching in NDN/ndnSIM

A reproducible ns-3/ndnSIM experiment for studying **Digital Twin (DT) state dissemination under application-specific freshness requirements**.

The repository compares four mechanisms under a common workload and topology:

| Code | Approach | Cache behavior |
|---|---|---|
| **A** | **IP/UDP - No Cache** | Every request retrieves DT state from the source |
| **B** | **NDN - No Cache** | NDN forwarding with Content Store disabled |
| **C** | **NDN - Native Cache** | Native NFD Content Store using producer `FreshnessPeriod` + `MustBeFresh` |
| **D** | **NDN - Freshness-Aware Cache (Proposed)** | Cached state is accepted only when its expected delivery age satisfies the request-specific freshness budget `F_max` |

The main purpose is to quantify the trade-off among **Age of Information (AoI), freshness violations, retrieval latency, cache reuse, and backhaul traffic**.

> This repository contains the simulation, NFD instrumentation, experiment runner, validation scripts, analysis pipeline, and publication-oriented plotting code.

## 1. Tested environment

The experiment was developed and validated with an ndnSIM tree whose ndnSIM commit is:

```text
90d5039
```

The environment checker identifies this as the ndnSIM 2.9 preparation tree with the NFD 22.02 / ndn-cxx 0.8.x API generation used by this implementation.

The scripts assume an ns-3 tree containing:

```text
<NS3_ROOT>/waf
<NS3_ROOT>/src/ndnSIM
<NS3_ROOT>/src/ndnSIM/NFD/daemon/fw/forwarder.cpp
```

Python dependencies:

```text
pandas
numpy
matplotlib
tabulate
```

## 2. Quick start

Assume:

```bash
export NS3_ROOT=/home/fablab/Desktop/ndnSIM/ns-3
```

Clone this repository and enter it:

```bash
git clone https://github.com/<YOUR-USERNAME>/dt-freshness-aware-ndn.git
cd dt-freshness-aware-ndn
```

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Check the ns-3/ndnSIM environment:

```bash
bash scripts/check_environment.sh "$NS3_ROOT"
```

Install the experiment into the ns-3 tree:

```bash
bash scripts/install_into_ns3.sh "$NS3_ROOT"
```

Apply the Arm-D freshness-aware NFD instrumentation:

```bash
python3 scripts/apply_freshness_patch.py "$NS3_ROOT"
```

Build:

```bash
cd "$NS3_ROOT"
./waf
```

Run the smoke test:

```bash
bash dt-study-tools/run_smoke_tests.sh "$NS3_ROOT"
```

The last line should be:

```text
Smoke validation PASS
```

Do **not** run the full matrix until the smoke validation passes.

## 3. Run one simulation

Example: proposed freshness-aware NDN with `F_max=100 ms`:

```bash
cd "$NS3_ROOT"
./waf --run="dt-freshness-study \
  --arm=D \
  --experiment=e1 \
  --run=1 \
  --simulationTime=60 \
  --warmupTime=5 \
  --updatePeriodMs=10 \
  --requestRateHz=10 \
  --requestJitterMs=5 \
  --requestTimeoutMs=80 \
  --freshnessDeliveryGuardMs=2 \
  --payloadBytes=512 \
  --cacheSize=1 \
  --fmaxMs=100 \
  --nativeFreshnessMs=500 \
  --outputRoot=single-run-results"
```

The run creates per-request and network-level CSV files under the specified result directory.

## 4. Run the complete paper matrix

The standard configuration uses:

- 20 paired repetitions;
- 60 s per simulation;
- 5 s warm-up;
- 10 requests/s;
- ±5 ms request jitter;
- 10 ms DT update period;
- 512-byte DT payload;
- MEC Content Store capacity of one packet;
- 80 ms request timeout;
- 2 ms freshness delivery guard.

Run:

```bash
cd "$NS3_ROOT"
python3 dt-study-tools/run_paper_experiments.py \
  --ns3-root "$NS3_ROOT" \
  --results-root paper-results-v2 \
  --runs 20
```

The matrix contains **320 configurations**:

- **E1:** A/B/C reference mechanisms plus D with `F_max ∈ {10,20,50,100,200,500,1000,2000} ms`;
- **E4:** heterogeneous freshness with strict `F_max=20 ms` and relaxed `F_max=500 ms`, including native NDN with global freshness periods of 20 ms and 500 ms.

The runner is resumable: completed runs are skipped unless `--force` is specified.

## 5. Analyze results

If analysis was skipped or you want to re-run it:

```bash
cd "$NS3_ROOT"
python3 dt-study-tools/analyze_results.py paper-results-v2
```

Important validation files:

```text
paper-results-v2/pairing-validation.csv
paper-results-v2/analysis-data-quality.csv
paper-results-v2/summary.csv
paper-results-v2/summary-ci95.csv
paper-results-v2/all-requests.csv
paper-results-v2/all-offered-requests.csv
paper-results-v2/all-timeouts.csv
```

Before using the results in a paper, verify that paired mechanisms use identical request IDs and send traces and that the expected run set completed successfully.

## 6. Generate figures

```bash
cd "$NS3_ROOT"
python3 dt-study-tools/make_paper_results.py \
  --results-root "$NS3_ROOT/paper-results-v2" \
  --skip-analyzer
```

The current plotting pipeline includes:

- freshness violation versus `F_max`;
- backhaul bytes per offered request versus `F_max`;
- complete AoI ECDFs for representative mechanisms;
- mean retrieval latency versus `F_max`;
- cache-served versus source-forwarded request ratio;
- latency and backhaul savings relative to NDN without caching;
- policy comparison plots using hatching patterns for grayscale readability;
- E4 strict/relaxed freshness and backhaul comparisons.

The analysis intentionally does **not** use p95 AoI or p95 latency. Complete request-level samples remain available in `all-requests.csv`; 95% confidence intervals across independent runs are used only as statistical uncertainty estimates.

## 7. Repository structure

```text
.
├── scratch/
│   └── dt-freshness-study.cc       # ns-3 simulation entry point
├── dt-study-src/
│   ├── experiment-config.hpp       # experiment configuration
│   ├── topology.hpp                # topology construction
│   ├── dt-state.hpp                # synthetic DT physical state
│   ├── wire-format.hpp             # DT state encoding
│   ├── ip-apps.hpp                 # IP/UDP applications
│   ├── ndn-apps.hpp                # NDN applications
│   ├── traffic-meter.hpp           # network/backhaul accounting
│   └── csv-logger.hpp              # run-level CSV logging
├── scripts/
│   ├── check_environment.sh
│   ├── install_into_ns3.sh
│   ├── apply_freshness_patch.py
│   ├── run_smoke_tests.sh
│   ├── run_paper_experiments.py
│   ├── analyze_results.py
│   └── make_paper_results.py
├── patches/
│   └── README.md
├── docs/
│   ├── TUTORIAL.md
│   ├── EXPERIMENTS.md
│   ├── OUTPUTS.md
│   └── GITHUB_PUBLISHING.md
├── DESIGN.md
├── SETUP.md
└── requirements.txt
```

## 8. Why Arm D modifies NFD Forwarder

A normal NFD forwarding strategy cannot reject a Content Store hit after NFD has already selected cached Data. Therefore Arm D instruments the NFD Forwarder Content Store hit/miss path.

For a cached DT object:

```text
expected_arrival_age = cached_state_age + downstream_delivery_guard
```

The cache hit is accepted only when:

```text
expected_arrival_age <= F_max
```

Otherwise the event is recorded as `STALE_REJECT` and the Interest is returned to NFD's normal cache-miss forwarding path.

`F_max` is carried in a simulation-only Interest Nonce encoding so strict and relaxed consumers can use the **same content name and shared cache key**. This is an experimental carrier and is not proposed as a production NDN wire-format mechanism.

## 9. Reverting the NFD modification

The patcher creates:

```text
forwarder.cpp.dtstudy.bak
```

Restore the original Forwarder with:

```bash
python3 scripts/apply_freshness_patch.py "$NS3_ROOT" --revert
```

Then rebuild:

```bash
cd "$NS3_ROOT"
./waf
```

## 10. Reproducibility notes

The runner writes experiment metadata, configuration, and version information with the results. Paired runs use the same offered request IDs and send timestamps across mechanisms. The default 80 ms timeout is below the minimum 95 ms request interval, preventing one mechanism's latency from suppressing the next offered request.

For the full explanation, see [`docs/TUTORIAL.md`](docs/TUTORIAL.md) and [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md).

## License

Before publishing the repository publicly, choose and add an explicit open-source license. MIT is a simple option for research code, but the appropriate license should be selected according to your institution, co-author, and dependency requirements.
