#!/usr/bin/env python3
"""
Run the paper-ready E1 + E4 experiment matrix for DT Freshness Study v0.3.1.

The simulator code is NOT modified by this script. It freezes one controlled
parameter set, executes paired runs, supports resume, and records a reproducible
manifest of every command.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

FMAX_VALUES_MS = [10, 20, 50, 100, 200, 500, 1000, 2000]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_value(path: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def expected_dir(
    output_root: Path,
    arm: str,
    experiment: str,
    run_id: int,
    fmax_ms: int,
    native_ms: int,
    cache_size: int,
    strict_ms: int = 20,
    relaxed_ms: int = 500,
) -> Path:
    if experiment == "e4":
        name = (
            f"{arm}-e4-strict{strict_ms}-relaxed{relaxed_ms}"
            f"-native{native_ms}-cache{cache_size}-run{run_id}"
        )
    else:
        name = (
            f"{arm}-e1-fmax{fmax_ms}"
            f"-native{native_ms}-cache{cache_size}-run{run_id}"
        )
    return output_root / name


def completed(run_dir: Path) -> bool:
    path = run_dir / "requests.csv"
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with path.open(newline="") as f:
            rows = sum(1 for _ in f)
        return rows >= 2
    except OSError:
        return False


def run_cmd(ns3_root: Path, args: str, log_file: Path, dry_run: bool) -> None:
    command = ["./waf", f"--run=dt-freshness-study {args}"]
    printable = " ".join(command)
    print("+", printable, flush=True)

    with log_file.open("a") as out:
        out.write(printable + "\n")

    if dry_run:
        return

    subprocess.run(command, cwd=str(ns3_root), check=True)


def matrix_rows(
    runs: int,
    simulation_time: float,
    warmup_time: float,
    output_root_name: str,
    request_rate_hz: float,
    update_period_ms: int,
    request_jitter_ms: float,
    payload_bytes: int,
    cache_size: int,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    common = {
        "simulation_time_s": simulation_time,
        "warmup_time_s": warmup_time,
        "request_rate_hz": request_rate_hz,
        "update_period_ms": update_period_ms,
        "request_jitter_ms": request_jitter_ms,
        "request_timeout_ms": 80,
        "freshness_delivery_guard_ms": 2.0,
        "payload_bytes": payload_bytes,
        "cache_size": cache_size,
        "output_root": output_root_name,
    }

    for run_id in range(1, runs + 1):
        # E1 reference arms: one network simulation per paired run.
        for arm in ("A", "B", "C"):
            rows.append(
                {
                    **common,
                    "experiment": "e1",
                    "arm": arm,
                    "run": run_id,
                    "fmax_ms": 100,
                    "native_freshness_ms": 500,
                    "strict_fmax_ms": 20,
                    "relaxed_fmax_ms": 500,
                }
            )

        # E1 proposed arm: sweep application freshness budget.
        for fmax_ms in FMAX_VALUES_MS:
            rows.append(
                {
                    **common,
                    "experiment": "e1",
                    "arm": "D",
                    "run": run_id,
                    "fmax_ms": fmax_ms,
                    "native_freshness_ms": 500,
                    "strict_fmax_ms": 20,
                    "relaxed_fmax_ms": 500,
                }
            )

        # E4 source-retrieval references.
        for arm in ("A", "B"):
            rows.append(
                {
                    **common,
                    "experiment": "e4",
                    "arm": arm,
                    "run": run_id,
                    "fmax_ms": 100,
                    "native_freshness_ms": 500,
                    "strict_fmax_ms": 20,
                    "relaxed_fmax_ms": 500,
                }
            )

        # Native NDN: test the two global producer freshness choices.
        for native_ms in (20, 500):
            rows.append(
                {
                    **common,
                    "experiment": "e4",
                    "arm": "C",
                    "run": run_id,
                    "fmax_ms": 100,
                    "native_freshness_ms": native_ms,
                    "strict_fmax_ms": 20,
                    "relaxed_fmax_ms": 500,
                }
            )

        # Proposed arm: distinct per-consumer budgets coexist.
        rows.append(
            {
                **common,
                "experiment": "e4",
                "arm": "D",
                "run": run_id,
                "fmax_ms": 100,
                "native_freshness_ms": 500,
                "strict_fmax_ms": 20,
                "relaxed_fmax_ms": 500,
            }
        )

    return rows


def args_string(row: Dict[str, object]) -> str:
    return (
        f"--arm={row['arm']} "
        f"--experiment={row['experiment']} "
        f"--run={row['run']} "
        f"--simulationTime={row['simulation_time_s']} "
        f"--warmupTime={row['warmup_time_s']} "
        f"--updatePeriodMs={row['update_period_ms']} "
        f"--requestRateHz={row['request_rate_hz']} "
        f"--requestJitterMs={row['request_jitter_ms']} "
        f"--requestTimeoutMs={row['request_timeout_ms']} "
        f"--freshnessDeliveryGuardMs={row['freshness_delivery_guard_ms']} "
        f"--payloadBytes={row['payload_bytes']} "
        f"--cacheSize={row['cache_size']} "
        f"--fmaxMs={row['fmax_ms']} "
        f"--strictFmaxMs={row['strict_fmax_ms']} "
        f"--relaxedFmaxMs={row['relaxed_fmax_ms']} "
        f"--nativeFreshnessMs={row['native_freshness_ms']} "
        f"--outputRoot={row['output_root']}"
    )


def write_reproducibility_manifest(
    ns3_root: Path,
    result_root: Path,
    config: Dict[str, object],
) -> None:
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "ns3_root": str(ns3_root),
        "ndnsim_commit": git_value(ns3_root / "src/ndnSIM", "rev-parse", "HEAD"),
        "ndnsim_branch": git_value(ns3_root / "src/ndnSIM", "branch", "--show-current"),
        "nfd_commit": git_value(ns3_root / "src/ndnSIM/NFD", "rev-parse", "HEAD"),
        "ndn_cxx_commit": git_value(ns3_root / "src/ndnSIM/ndn-cxx", "rev-parse", "HEAD"),
        "experiment_config": config,
        "sha256": {},
    }

    important = [
        ns3_root / "scratch/dt-freshness-study.cc",
        ns3_root / "dt-study-src/experiment-config.hpp",
        ns3_root / "dt-study-src/ndn-apps.hpp",
        ns3_root / "dt-study-src/ip-apps.hpp",
        ns3_root / "dt-study-src/dt-state.hpp",
        ns3_root / "dt-study-src/traffic-meter.hpp",
        ns3_root / "src/ndnSIM/NFD/daemon/fw/forwarder.cpp",
    ]
    for path in important:
        if path.exists():
            manifest["sha256"][str(path.relative_to(ns3_root))] = sha256(path)

    (result_root / "reproducibility-manifest.json").write_text(
        json.dumps(manifest, indent=2)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns3-root", required=True)
    parser.add_argument("--results-root", default="paper-results-v2")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--simulation-time", type=float, default=60.0)
    parser.add_argument("--warmup-time", type=float, default=5.0)
    parser.add_argument("--request-rate-hz", type=float, default=10.0)
    parser.add_argument("--update-period-ms", type=int, default=10)
    parser.add_argument("--request-jitter-ms", type=float, default=5.0)
    parser.add_argument("--payload-bytes", type=int, default=512)
    parser.add_argument("--cache-size", type=int, default=1)
    parser.add_argument("--force", action="store_true",
                        help="Re-run configurations even when requests.csv exists.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-analysis", action="store_true")
    args = parser.parse_args()

    ns3_root = Path(args.ns3_root).expanduser().resolve()
    if not (ns3_root / "waf").exists():
        raise SystemExit(f"waf not found in {ns3_root}")

    scenario = ns3_root / "scratch/dt-freshness-study.cc"
    if not scenario.exists():
        raise SystemExit(f"Scenario not found: {scenario}")

    forwarder = ns3_root / "src/ndnSIM/NFD/daemon/fw/forwarder.cpp"
    if not forwarder.exists() or "dtDecodeFreshnessBudgetMs" not in forwarder.read_text():
        raise SystemExit(
            "Arm-D Forwarder instrumentation is not installed. "
            "Apply dt-study-tools/apply_freshness_patch.py first."
        )

    output_root_name = args.results_root
    if "/" in output_root_name or output_root_name in {".", ".."}:
        raise SystemExit(
            "--results-root must be a single directory name relative to the ns-3 root "
            "(example: paper-results-v2)."
        )

    result_root = ns3_root / output_root_name
    result_root.mkdir(exist_ok=True)

    config = {
        "runs": args.runs,
        "simulation_time_s": args.simulation_time,
        "warmup_time_s": args.warmup_time,
        "request_rate_hz": args.request_rate_hz,
        "update_period_ms": args.update_period_ms,
        "request_jitter_ms": args.request_jitter_ms,
        "request_timeout_ms": 80,
        "freshness_delivery_guard_ms": 2.0,
        "payload_bytes": args.payload_bytes,
        "cache_size_packets": args.cache_size,
        "e1_fmax_values_ms": FMAX_VALUES_MS,
        "e1_native_freshness_ms": 500,
        "e4_strict_fmax_ms": 20,
        "e4_relaxed_fmax_ms": 500,
        "e4_native_freshness_values_ms": [20, 500],
    }
    (result_root / "paper-experiment-config.json").write_text(
        json.dumps(config, indent=2)
    )
    write_reproducibility_manifest(ns3_root, result_root, config)

    rows = matrix_rows(
        args.runs,
        args.simulation_time,
        args.warmup_time,
        output_root_name,
        args.request_rate_hz,
        args.update_period_ms,
        args.request_jitter_ms,
        args.payload_bytes,
        args.cache_size,
    )

    with (result_root / "experiment-matrix.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    log_file = result_root / "commands.log"
    total = len(rows)
    executed = 0
    skipped = 0

    for index, row in enumerate(rows, start=1):
        run_dir = expected_dir(
            result_root,
            str(row["arm"]),
            str(row["experiment"]),
            int(row["run"]),
            int(row["fmax_ms"]),
            int(row["native_freshness_ms"]),
            int(row["cache_size"]),
            int(row["strict_fmax_ms"]),
            int(row["relaxed_fmax_ms"]),
        )

        print(
            f"\n[{index}/{total}] "
            f"{row['experiment'].upper()} arm={row['arm']} run={row['run']} "
            f"Fmax={row['fmax_ms']} native={row['native_freshness_ms']}"
        )

        if not args.force and completed(run_dir):
            print(f"  SKIP complete: {run_dir.name}")
            skipped += 1
            continue

        run_cmd(ns3_root, args_string(row), log_file, args.dry_run)
        executed += 1

    print(f"\nMatrix complete: executed={executed}, skipped={skipped}, total={total}")

    if args.dry_run or args.skip_analysis:
        return

    analyzer = ns3_root / "dt-study-tools/analyze_results.py"
    paper = ns3_root / "dt-study-tools/make_paper_results.py"

    if not analyzer.exists():
        raise SystemExit(f"Analyzer not found: {analyzer}")

    subprocess.run(
        [sys.executable, str(analyzer), str(result_root)],
        cwd=str(ns3_root),
        check=True,
    )

    if paper.exists():
        subprocess.run(
            [
                sys.executable,
                str(paper),
                "--results-root",
                str(result_root),
                "--skip-analyzer",
            ],
            cwd=str(ns3_root),
            check=True,
        )
    else:
        print(
            "Paper figure generator not installed yet. "
            "Run make_paper_results.py after copying it to dt-study-tools/."
        )


if __name__ == "__main__":
    main()
