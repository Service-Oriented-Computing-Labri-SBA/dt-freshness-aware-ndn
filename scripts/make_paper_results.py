#!/usr/bin/env python3
"""
Paper-figure generator for DT Freshness Study v0.3.x.

Design principles:
- Keep every request-level AoI/latency sample.
- Draw ECDFs as statistical step functions; never spline/KDE smooth them.
- Use a reduced set of operating points in main comparison figures.
- Keep the complete F_max sweep in sensitivity figures/tables.
- Emphasize the freshness-efficiency trade-off directly.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ORDER = ["A", "B", "C", "D"]

NAMES = {
    "A": "IP/UDP - No Cache",
    "B": "NDN - No Cache",
    "C": "NDN - Native Cache",
    "D": "NDN - Freshness-Aware Cache (Proposed)",
}

# Main-paper operating points. The complete sweep remains in tables and
# dedicated sensitivity figures.
E1_MAIN_D_FMAX = [100, 500, 2000]
E1_SENSITIVITY_FMAX = [50, 100, 200, 500, 1000]

# Distinguish multiple D operating points without artificially smoothing data.
D_LINESTYLES = ["-", "--", "-.", ":", "-", "--", "-.", ":"]
D_MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]


# Policy-specific hatching.  These patterns are intentionally redundant with
# color so figures remain readable in grayscale/print.
POLICY_HATCH = {
    "A": "///",          # IP/UDP - No Cache
    "B": "\\\\\\",       # NDN - No Cache
    "C": "xx",           # NDN - Native Cache
    "C-native20": "xx",
    "C-native500": "..",
    "D": "++",           # Proposed freshness-aware cache
}

# Hatches for serving-path composition.
PATH_HATCH = {
    "cache": "///",
    "source": "...",
}


def ci95(series):
    s = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    return math.nan if len(s) < 2 else float(1.96 * s.std(ddof=1) / math.sqrt(len(s)))


def mean_ci(series):
    s = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if s.empty:
        return math.nan, math.nan
    return float(s.mean()), ci95(s)


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def ecdf(values):
    x = np.sort(pd.to_numeric(values, errors="coerce").dropna().to_numpy(float))
    if len(x) == 0:
        return x, np.array([])
    y = np.arange(1, len(x) + 1, dtype=float) / len(x)
    return x, y


def draw_ecdf(ax, values, label, **kwargs):
    """Statistically correct staircase ECDF."""
    x, y = ecdf(values)
    if len(x) == 0:
        return
    # Add y=0 at the first observed x to make the step interpretation explicit.
    xx = np.r_[x[0], x]
    yy = np.r_[0.0, y]
    ax.step(xx, yy, where="post", label=label, **kwargs)


def variant(row):
    return f"C-native{int(row['native_freshness_ms'])}" if row["arm"] == "C" else str(row["arm"])


def vlabel(v):
    return {
        "A": "IP/UDP - No Cache",
        "B": "NDN - No Cache",
        "C-native20": "NDN - Native Cache (FreshnessPeriod=20 ms)",
        "C-native500": "NDN - Native Cache (FreshnessPeriod=500 ms)",
        "D": "NDN - Freshness-Aware Cache (Proposed)",
    }.get(v, v)


def build_e1(root, summary):
    refs = pd.read_csv(root / "e1-reference-thresholds.csv")
    rows = []

    metrics = [
        "latency_ms_mean", "latency_ms_median", "latency_ms_min", "latency_ms_max", "latency_ms_std",
        "aoi_ms_mean", "aoi_ms_median", "aoi_ms_min", "aoi_ms_max", "aoi_ms_std",
        "dt_error_mean",
        "cache_hit_ratio_request_level",
        "valid_cache_hit_ratio_request_level",
        "backhaul_bytes_per_offered_request_run",
        "satisfaction_ratio",
        "timeout_ratio",
    ]

    for arm in ["A", "B", "C"]:
        group = summary[(summary.experiment == "e1") & (summary.arm == arm)]
        base = {}
        for metric in metrics:
            base[metric], base[metric + "_ci95"] = mean_ci(group[metric])

        for threshold, threshold_group in refs[refs.arm == arm].groupby("evaluation_fmax_ms"):
            fvr, fvr_ci = mean_ci(threshold_group.freshness_violation_ratio)
            rows.append({
                "arm": arm,
                "approach_name": NAMES[arm],
                "fmax_ms": float(threshold),
                "freshness_violation_ratio": fvr,
                "freshness_violation_ratio_ci95": fvr_ci,
                **base,
            })

    proposed = summary[(summary.experiment == "e1") & (summary.arm == "D")]
    for threshold, group in proposed.groupby("fmax_ms"):
        row = {
            "arm": "D",
            "approach_name": NAMES["D"],
            "fmax_ms": float(threshold),
        }
        for metric in ["freshness_violation_ratio"] + metrics:
            row[metric], row[metric + "_ci95"] = mean_ci(group[metric])
        rows.append(row)

    out = pd.DataFrame(rows).sort_values(["arm", "fmax_ms"])
    out.to_csv(root / "paper-table-e1.csv", index=False)
    return out


def build_e4(root, summary):
    e4 = summary[summary.experiment == "e4"].copy()
    e4["variant"] = e4.apply(variant, axis=1)

    metrics = [
        "freshness_violation_ratio",
        "latency_ms_mean", "latency_ms_median", "latency_ms_min", "latency_ms_max", "latency_ms_std",
        "aoi_ms_mean", "aoi_ms_median", "aoi_ms_min", "aoi_ms_max", "aoi_ms_std",
        "dt_error_mean",
        "cache_hit_ratio_request_level",
        "valid_cache_hit_ratio_request_level",
        "freshness_valid_hit_ratio",
        "stale_reject_request_ratio",
        "backhaul_bytes_per_offered_request_run",
        "satisfaction_ratio",
        "timeout_ratio",
    ]

    rows = []
    for (v, consumer), group in e4.groupby(["variant", "consumer"]):
        row = {
            "variant": v,
            "approach_name": vlabel(v),
            "consumer": consumer,
            "n_runs": int(group.run.nunique()),
        }
        for metric in metrics:
            row[metric], row[metric + "_ci95"] = mean_ci(group[metric])
        rows.append(row)

    order = {"A": 0, "B": 1, "C-native20": 2, "C-native500": 3, "D": 4}
    out = pd.DataFrame(rows)
    out["_order"] = out.variant.map(order)
    out = out.sort_values(["_order", "consumer"]).drop(columns="_order")
    out.to_csv(root / "paper-table-e4.csv", index=False)
    return out


def e1_curve(root, table, metric, ci_metric, ylabel, filename):
    """Full F_max mechanism-level sweep."""
    fig, ax = plt.subplots(figsize=(8.2, 4.8))

    for arm in ORDER:
        group = table[table.arm == arm].sort_values("fmax_ms")
        ax.errorbar(
            group.fmax_ms,
            group[metric],
            yerr=group[ci_metric],
            marker="o",
            capsize=3,
            label=NAMES[arm],
        )

    ax.set_xscale("log")
    ax.set_xlabel(r"Freshness budget $F_{\max}$ (ms)")
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(fontsize=9)
    save(fig, root / filename)


def e1_main_ecdf(root, all_requests, metric, xlabel, filename):
    """
    Main-paper ECDF:
    A/B/C plus only three representative D operating points.
    """
    e1 = all_requests[all_requests.experiment == "e1"]
    fig, ax = plt.subplots(figsize=(8.6, 5.0))

    for arm in ["A", "B", "C"]:
        draw_ecdf(ax, e1[e1.arm == arm][metric], NAMES[arm], linewidth=2)

    for i, fmax in enumerate(E1_MAIN_D_FMAX):
        draw_ecdf(
            ax,
            e1[(e1.arm == "D") & (e1.fmax_ms == fmax)][metric],
            f"Proposed - $F_{{\\max}}$={fmax} ms",
            linewidth=2,
            linestyle=D_LINESTYLES[i],
        )

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Empirical CDF")
    ax.set_ylim(0, 1.01)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, loc="best")
    save(fig, root / filename)


def e1_proposed_aoi_sensitivity(root, all_requests):
    """
    D-only AoI ECDF with a curated F_max subset and vertical budget markers.
    This demonstrates that the observed state-age distribution is controlled
    by the application freshness budget.
    """
    e1 = all_requests[
        (all_requests.experiment == "e1")
        & (all_requests.arm == "D")
        & (all_requests.fmax_ms.isin(E1_SENSITIVITY_FMAX))
    ]

    fig, ax = plt.subplots(figsize=(8.6, 5.0))

    for i, fmax in enumerate(E1_SENSITIVITY_FMAX):
        values = e1[e1.fmax_ms == fmax]["aoi_ms"]
        draw_ecdf(
            ax,
            values,
            f"$F_{{\\max}}$={fmax} ms",
            linewidth=2,
            linestyle=D_LINESTYLES[i],
        )
        # Marker for the requested freshness limit; not a smoothed fit.
        ax.axvline(fmax, linestyle=":", linewidth=1, alpha=0.35)

    ax.set_xlabel("Age of Information (ms)")
    ax.set_ylabel("Empirical CDF")
    ax.set_ylim(0, 1.01)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, ncol=2)
    save(fig, root / "fig-e1-proposed-aoi-ecdf")


def e1_cache_service_ratio(root, table):
    """
    Replace the visually weak proposed-latency ECDF with the mechanism that
    actually causes the two latency modes: cache-served vs source-served.
    """
    d = table[table.arm == "D"].sort_values("fmax_ms").copy()

    cache = pd.to_numeric(d["cache_hit_ratio_request_level"], errors="coerce").fillna(0).clip(0, 1)
    source = (1.0 - cache).clip(0, 1)

    labels = [str(int(x)) for x in d.fmax_ms]
    x = np.arange(len(d))

    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    ax.bar(x, cache, label="Served from MEC cache")
    ax.bar(x, source, bottom=cache, label="Forwarded toward DT source")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel(r"Freshness budget $F_{\max}$ (ms)")
    ax.set_ylabel("Fraction of satisfied requests")
    ax.set_ylim(0, 1.0)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    save(fig, root / "fig-e1-proposed-cache-source-ratio")


def e1_pareto(root, table):
    """
    Freshness-efficiency operating-space figure.

    Lower-left is preferable:
      x -> lower backhaul
      y -> fewer freshness violations

    D points are annotated by F_max.
    """
    fig, ax = plt.subplots(figsize=(7.7, 5.2))

    # A/B/C at the 500-ms evaluation threshold provides a consistent reference
    # point without repeating the same network point eight times.
    ref_threshold = 500
    for arm in ["A", "B", "C"]:
        group = table[(table.arm == arm) & (table.fmax_ms == ref_threshold)]
        if group.empty:
            continue
        row = group.iloc[0]
        ax.scatter(
            row["backhaul_bytes_per_offered_request_run"],
            row["freshness_violation_ratio"],
            s=70,
            marker="o",
            label=NAMES[arm],
        )

    d = table[table.arm == "D"].sort_values("fmax_ms")
    ax.plot(
        d["backhaul_bytes_per_offered_request_run"],
        d["freshness_violation_ratio"],
        marker="o",
        linewidth=1.8,
        label=NAMES["D"],
    )

    for _, row in d.iterrows():
        ax.annotate(
            f"{int(row.fmax_ms)}",
            (
                row["backhaul_bytes_per_offered_request_run"],
                row["freshness_violation_ratio"],
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=7,
        )

    ax.set_xlabel("Backhaul bytes / offered request")
    ax.set_ylabel("Freshness violation ratio")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    ax.text(
        0.02,
        0.03,
        r"Labels on proposed curve = $F_{\max}$ (ms)",
        transform=ax.transAxes,
        fontsize=8,
    )
    save(fig, root / "fig-e1-freshness-backhaul-pareto")



def e1_latency_vs_fmax(root, table):
    """
    Mean retrieval latency versus F_max.

    A/B/C are fixed baselines; D changes with the application freshness budget.
    This is the clearest primary latency figure for the paper.
    """
    fig, ax = plt.subplots(figsize=(8.2, 4.8))

    style = {
        "A": {"marker": "o", "linestyle": "-",  "linewidth": 1.8},
        "B": {"marker": "s", "linestyle": "--", "linewidth": 1.8},
        "C": {"marker": "^", "linestyle": "-.", "linewidth": 1.8},
        "D": {"marker": "D", "linestyle": "-",  "linewidth": 2.4},
    }

    for arm in ORDER:
        group = table[table.arm == arm].sort_values("fmax_ms")
        ax.errorbar(
            group.fmax_ms,
            group["latency_ms_mean"],
            yerr=group["latency_ms_mean_ci95"],
            capsize=3,
            label=NAMES[arm],
            **style[arm],
        )

    ax.set_xscale("log")
    ax.set_xlabel(r"Freshness budget $F_{\max}$ (ms)")
    ax.set_ylabel("Mean retrieval latency (ms)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(fontsize=8)
    save(fig, root / "fig-e1-mean-latency")


def e1_cache_source_ratio(root, table):
    """
    100% stacked serving-path composition for the proposed method.

    The bar height is always 1.0:
      lower segment = served by MEC cache
      upper segment = forwarded toward DT source

    Hatching is used because the figure should remain clear without color.
    """
    d = table[table.arm == "D"].sort_values("fmax_ms").copy()

    cache = (
        pd.to_numeric(d["cache_hit_ratio_request_level"], errors="coerce")
        .fillna(0)
        .clip(0, 1)
    )
    source = (1.0 - cache).clip(0, 1)

    labels = [str(int(v)) for v in d.fmax_ms]
    x = np.arange(len(d))

    fig, ax = plt.subplots(figsize=(8.8, 4.8))

    ax.bar(
        x,
        cache,
        edgecolor="black",
        linewidth=0.8,
        hatch=PATH_HATCH["cache"],
        label="Served from MEC cache",
    )
    ax.bar(
        x,
        source,
        bottom=cache,
        edgecolor="black",
        linewidth=0.8,
        hatch=PATH_HATCH["source"],
        label="Forwarded to DT source",
    )

    # Add percentages inside bars when there is enough room.
    for i, (c, s) in enumerate(zip(cache, source)):
        if c >= 0.08:
            ax.text(i, c / 2.0, f"{100*c:.0f}%", ha="center", va="center", fontsize=8)
        if s >= 0.08:
            ax.text(i, c + s / 2.0, f"{100*s:.0f}%", ha="center", va="center", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel(r"Freshness budget $F_{\max}$ (ms)")
    ax.set_ylabel("Fraction of satisfied requests")
    ax.set_ylim(0, 1)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=9)
    save(fig, root / "fig-e1-proposed-cache-source-ratio")


def e1_savings_vs_fmax(root, table):
    """
    Latency and backhaul savings of D relative to NDN-NoCache (B).

    Savings are reported as percentages:
      0%   = same as NDN-NoCache
      50%  = half the cost
      100% = complete elimination of the measured cost
    """
    d = table[table.arm == "D"].sort_values("fmax_ms").copy()
    b = table[table.arm == "B"].iloc[0]

    b_latency = float(b["latency_ms_mean"])
    b_backhaul = float(b["backhaul_bytes_per_offered_request_run"])

    latency_saving = 100.0 * (
        1.0 - pd.to_numeric(d["latency_ms_mean"], errors="coerce") / b_latency
    )
    backhaul_saving = 100.0 * (
        1.0
        - pd.to_numeric(d["backhaul_bytes_per_offered_request_run"], errors="coerce")
        / b_backhaul
    )

    labels = [str(int(v)) for v in d.fmax_ms]
    x = np.arange(len(d))
    width = 0.38

    fig, ax = plt.subplots(figsize=(9.0, 4.8))

    ax.bar(
        x - width / 2,
        latency_saving,
        width,
        edgecolor="black",
        linewidth=0.8,
        hatch="///",
        label="Latency saving vs NDN - No Cache",
    )
    ax.bar(
        x + width / 2,
        backhaul_saving,
        width,
        edgecolor="black",
        linewidth=0.8,
        hatch="xx",
        label="Backhaul saving vs NDN - No Cache",
    )

    ax.axhline(0, linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel(r"Freshness budget $F_{\max}$ (ms)")
    ax.set_ylabel("Saving relative to NDN - No Cache (%)")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    save(fig, root / "fig-e1-latency-backhaul-savings")


def e1_policy_latency_bars(root, table, selected_fmax=500):
    """
    Representative policy comparison at one application freshness budget.

    Policy-specific hatching is used for grayscale-safe publication.
    """
    rows = []

    for arm in ["A", "B", "C"]:
        g = table[(table.arm == arm) & (table.fmax_ms == selected_fmax)]
        if not g.empty:
            rows.append(g.iloc[0])

    gd = table[(table.arm == "D") & (table.fmax_ms == selected_fmax)]
    if not gd.empty:
        rows.append(gd.iloc[0])

    if not rows:
        return

    labels = [
        "IP/UDP\nNo Cache",
        "NDN\nNo Cache",
        "NDN\nNative Cache",
        f"Proposed NDN\n$F_{{\\max}}$={selected_fmax} ms",
    ]

    values = [float(r["latency_ms_mean"]) for r in rows]
    cis = [float(r["latency_ms_mean_ci95"]) for r in rows]
    arms = [str(r["arm"]) for r in rows]

    fig, ax = plt.subplots(figsize=(7.8, 4.6))

    bars = ax.bar(
        np.arange(len(values)),
        values,
        yerr=cis,
        capsize=3,
        edgecolor="black",
        linewidth=0.9,
    )

    for bar, arm in zip(bars, arms):
        bar.set_hatch(POLICY_HATCH[arm])

    ax.set_xticks(np.arange(len(values)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Mean retrieval latency (ms)")
    ax.grid(True, axis="y", alpha=0.25)
    save(fig, root / f"fig-e1-policy-latency-fmax{selected_fmax}")


def e1_latency_mode_summary(root, all_requests):
    """
    Optional diagnostic view showing the two dominant latency modes directly.

    Uses a histogram for representative operating points rather than ECDF,
    making the ~2 ms cache path and ~14.5 ms source path visually explicit.
    """
    e1 = all_requests[all_requests.experiment == "e1"]

    selections = [
        ("B", None, "NDN - No Cache"),
        ("C", None, "NDN - Native Cache"),
        ("D", 100, r"Proposed $F_{\max}=100$ ms"),
        ("D", 500, r"Proposed $F_{\max}=500$ ms"),
        ("D", 2000, r"Proposed $F_{\max}=2000$ ms"),
    ]

    fig, ax = plt.subplots(figsize=(8.4, 4.8))

    bins = np.linspace(
        float(pd.to_numeric(e1.latency_ms, errors="coerce").min()),
        float(pd.to_numeric(e1.latency_ms, errors="coerce").max()),
        45,
    )

    for arm, fmax, label in selections:
        g = e1[e1.arm == arm]
        if fmax is not None:
            g = g[g.fmax_ms == fmax]
        vals = pd.to_numeric(g.latency_ms, errors="coerce").dropna()
        if vals.empty:
            continue
        ax.hist(
            vals,
            bins=bins,
            histtype="step",
            density=True,
            linewidth=1.8,
            label=label,
        )

    ax.set_xlabel("Retrieval latency (ms)")
    ax.set_ylabel("Density")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    save(fig, root / "fig-e1-latency-mode-histogram")



def e4_fvr(root, table):
    variants = ["A", "B", "C-native20", "C-native500", "D"]
    labels = [
        "IP/UDP\nNo Cache",
        "NDN\nNo Cache",
        "NDN Native Cache\nFP=20 ms",
        "NDN Native Cache\nFP=500 ms",
        "Proposed NDN\nFreshness-Aware Cache",
    ]
    x = np.arange(len(variants))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9.7, 4.8))

    for j, consumer in enumerate(["strict", "relaxed"]):
        values, cis = [], []
        for v in variants:
            group = table[(table.variant == v) & (table.consumer == consumer)]
            values.append(float(group.freshness_violation_ratio.iloc[0]))
            cis.append(float(group.freshness_violation_ratio_ci95.iloc[0]))

        bars = ax.bar(
            x + (j - 0.5) * width,
            values,
            width,
            yerr=cis,
            capsize=3,
            edgecolor="black",
            linewidth=0.8,
            label=consumer.capitalize(),
        )
        for bar, policy in zip(bars, variants):
            bar.set_hatch(POLICY_HATCH[policy])

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Freshness violation ratio")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    save(fig, root / "fig-e4-freshness-violation")


def e4_ecdf(root, all_requests, consumer, metric, xlabel, filename):
    e4 = all_requests[
        (all_requests.experiment == "e4") & (all_requests.consumer == consumer)
    ].copy()
    e4["variant"] = e4.apply(variant, axis=1)

    fig, ax = plt.subplots(figsize=(8.3, 4.8))

    for v in ["A", "B", "C-native20", "C-native500", "D"]:
        draw_ecdf(
            ax,
            e4[e4.variant == v][metric],
            vlabel(v),
            linewidth=2,
        )

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Empirical CDF")
    ax.set_ylim(0, 1.01)
    ax.set_title(consumer.capitalize() + " consumer")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, loc="best")
    save(fig, root / filename)


def e4_backhaul(root, table):
    # Backhaul is run-level/system-level, so one consumer row per variant is
    # enough to avoid double counting.
    group = table[table.consumer == "strict"]

    variants = ["A", "B", "C-native20", "C-native500", "D"]
    labels = [
        "IP/UDP\nNo Cache",
        "NDN\nNo Cache",
        "NDN Native\nFP=20",
        "NDN Native\nFP=500",
        "Proposed NDN\nFA Cache",
    ]

    values, cis = [], []
    for v in variants:
        row = group[group.variant == v]
        values.append(float(row.backhaul_bytes_per_offered_request_run.iloc[0]))
        cis.append(float(row.backhaul_bytes_per_offered_request_run_ci95.iloc[0]))

    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(
        np.arange(len(variants)),
        values,
        yerr=cis,
        capsize=3,
        edgecolor="black",
        linewidth=0.9,
    )
    for bar, policy in zip(bars, variants):
        bar.set_hatch(POLICY_HATCH[policy])
    ax.set_xticks(np.arange(len(variants)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Backhaul bytes / offered request")
    ax.grid(True, axis="y", alpha=0.25)
    save(fig, root / "fig-e4-backhaul")


def validate(root, summary):
    pairing = pd.read_csv(root / "pairing-validation.csv")
    bad = pairing[
        (pairing.exact_send_trace_match != 1)
        | (pairing.exact_request_id_match != 1)
    ]

    checks = [
        {
            "check": "identical_offered_request_trace",
            "status": "PASS" if bad.empty else "FAIL",
            "details": f"{len(bad)} mismatches",
        },
        {
            "check": "no_timeouts",
            "status": "PASS" if int(summary.n_timeouts.sum()) == 0 else "FAIL",
            "details": f"{int(summary.n_timeouts.sum())} timeout rows",
        },
        {
            "check": "e1_repetitions",
            "status": "PASS" if summary[summary.experiment == "e1"].run.nunique() >= 20 else "WARN",
            "details": f"{summary[summary.experiment == 'e1'].run.nunique()} runs",
        },
        {
            "check": "e4_repetitions",
            "status": "PASS" if summary[summary.experiment == "e4"].run.nunique() >= 20 else "WARN",
            "details": f"{summary[summary.experiment == 'e4'].run.nunique()} runs",
        },
    ]

    out = pd.DataFrame(checks)
    out.to_csv(root / "paper-validation.csv", index=False)
    return out


def write_results_note(root, validation):
    note = """# Paper Results - Improved Figure Set

Approaches:

- A = IP/UDP - No Cache
- B = NDN - No Cache
- C = NDN - Native Cache
- D = NDN - Freshness-Aware Cache (Proposed)

## Figure policy

AoI and latency distributions are shown as empirical step CDFs. No spline,
polynomial, moving-average, KDE, or other artificial smoothing is applied.

The main E1 distribution comparison shows representative proposed operating
points at F_max = 100, 500, and 2000 ms. The full proposed sensitivity is
preserved in the dedicated AoI sensitivity figure and CSV tables.

Generated highlights:

- fig-e1-freshness-violation
- fig-e1-backhaul
- fig-e1-aoi-ecdf-main
- fig-e1-latency-ecdf-main
- fig-e1-proposed-aoi-ecdf
- fig-e1-proposed-cache-source-ratio
- fig-e1-freshness-backhaul-pareto
- fig-e4-freshness-violation
- fig-e4-backhaul
- E4 strict/relaxed AoI and latency ECDFs

"""
    (root / "PAPER_RESULTS.md").write_text(note + "\n" + validation.to_markdown(index=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--ns3-root")
    parser.add_argument("--skip-analyzer", action="store_true")
    args = parser.parse_args()

    root = Path(args.results_root).expanduser().resolve()

    if not args.skip_analyzer:
        if not args.ns3_root:
            raise SystemExit("--ns3-root required unless --skip-analyzer")
        subprocess.run(
            [
                sys.executable,
                str(Path(args.ns3_root) / "dt-study-tools/analyze_results.py"),
                str(root),
            ],
            check=True,
        )

    summary = pd.read_csv(root / "summary.csv")
    all_requests = pd.read_csv(root / "all-requests.csv")

    e1 = build_e1(root, summary)
    e4 = build_e4(root, summary)
    validation = validate(root, summary)

    # Core E1 trade-off.
    e1_curve(
        root,
        e1,
        "freshness_violation_ratio",
        "freshness_violation_ratio_ci95",
        "Freshness violation ratio",
        "fig-e1-freshness-violation",
    )
    e1_curve(
        root,
        e1,
        "backhaul_bytes_per_offered_request_run",
        "backhaul_bytes_per_offered_request_run_ci95",
        "Backhaul bytes / offered request",
        "fig-e1-backhaul",
    )

    # Reduced, publication-friendly full-distribution comparisons.
    e1_main_ecdf(
        root,
        all_requests,
        "aoi_ms",
        "Age of Information (ms)",
        "fig-e1-aoi-ecdf-main",
    )
    e1_main_ecdf(
        root,
        all_requests,
        "latency_ms",
        "Retrieval latency (ms)",
        "fig-e1-latency-ecdf-main",
    )

    # Proposed-method sensitivity and mechanism explanation.
    e1_proposed_aoi_sensitivity(root, all_requests)

    # Latency/performance views designed for the discrete cache/source modes.
    e1_latency_vs_fmax(root, e1)
    e1_cache_source_ratio(root, e1)
    e1_savings_vs_fmax(root, e1)
    e1_policy_latency_bars(root, e1, selected_fmax=500)
    e1_latency_mode_summary(root, all_requests)

    # Keep the operating-space plot available as a secondary diagnostic.
    e1_pareto(root, e1)

    # E4 heterogeneous freshness.
    e4_fvr(root, e4)
    e4_backhaul(root, e4)

    for consumer in ["strict", "relaxed"]:
        e4_ecdf(
            root,
            all_requests,
            consumer,
            "aoi_ms",
            "Age of Information (ms)",
            f"fig-e4-aoi-ecdf-{consumer}",
        )
        e4_ecdf(
            root,
            all_requests,
            consumer,
            "latency_ms",
            "Retrieval latency (ms)",
            f"fig-e4-latency-ecdf-{consumer}",
        )

    write_results_note(root, validation)
    print("Improved paper figures written to", root)


if __name__ == "__main__":
    main()
