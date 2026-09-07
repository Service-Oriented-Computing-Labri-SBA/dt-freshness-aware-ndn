#!/usr/bin/env python3
"""
Instrument ndnSIM 2.9-era / NFD Content Store processing for the DT freshness study.

Responsibilities:
  1. record real NFD HIT/MISS/STALE_REJECT events to cache-events.csv;
  2. for Arm D only, reject a cached DT state when expected arrival age > F_max.

The patcher supports both NFD Forwarder API layouts encountered in ndnSIM
2.x trees:

  Interest-first (ndnSIM/NFD 0.7.x):
    onContentStoreMiss(interest, ingress, pitEntry)
    onContentStoreHit(interest, ingress, pitEntry, data)

  Ingress-first (older ndnSIM/NFD trees):
    onContentStoreMiss(ingress, pitEntry, interest)
    onContentStoreHit(ingress, pitEntry, interest, data)

The original source signatures are preserved. Instrumentation is inserted just
inside the function bodies, avoiding brittle whole-signature replacement.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil

INCLUDE_ANCHOR = '#include <ndn-cxx/lp/tags.hpp>\n'
LOG_ANCHOR = 'NFD_LOG_INIT(Forwarder);\n'

MISS_INTEREST_FIRST_RE = re.compile(
    r"Forwarder::onContentStoreMiss\(\s*const Interest&\s+interest\s*,\s*"
    r"const FaceEndpoint&\s+ingress\s*,\s*"
    r"const shared_ptr<pit::Entry>&\s+pitEntry\s*\)\s*\{",
    re.MULTILINE,
)

HIT_INTEREST_FIRST_RE = re.compile(
    r"Forwarder::onContentStoreHit\(\s*const Interest&\s+interest\s*,\s*"
    r"const FaceEndpoint&\s+ingress\s*,\s*"
    r"const shared_ptr<pit::Entry>&\s+pitEntry\s*,\s*"
    r"const Data&\s+data\s*\)\s*\{",
    re.MULTILINE,
)

MISS_INGRESS_FIRST_RE = re.compile(
    r"Forwarder::onContentStoreMiss\(\s*const FaceEndpoint&\s+ingress\s*,\s*"
    r"const shared_ptr<pit::Entry>&\s+pitEntry\s*,\s*"
    r"const Interest&\s+interest\s*\)\s*\{",
    re.MULTILINE,
)

HIT_INGRESS_FIRST_RE = re.compile(
    r"Forwarder::onContentStoreHit\(\s*const FaceEndpoint&\s+ingress\s*,\s*"
    r"const shared_ptr<pit::Entry>&\s+pitEntry\s*,\s*"
    r"const Interest&\s+interest\s*,\s*"
    r"const Data&\s+data\s*\)\s*\{",
    re.MULTILINE,
)

EXTRA_INCLUDES = '''#include <ndn-cxx/lp/tags.hpp>
#include "ns3/simulator.h"

#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <string>
'''

HELPERS = r'''
// --------------------------------------------------------------------------
// DT freshness-study support (simulation only).
//
// Arm-D nonce layout:
//   31..24 : 0xFD marker
//   23..12 : F_max in milliseconds
//   11..10 : consumer identifier
//    9.. 0 : request sequence
//
// The content name remains unchanged across consumers, allowing E4 to test
// different freshness budgets against one shared MEC Content Store state.
// --------------------------------------------------------------------------
static uint32_t
dtNonceToUint32(const Interest& interest)
{
  const auto nonce = interest.getNonce();

  // ndn-cxx 0.8.x represents Nonce as four bytes in network byte order.
  return (static_cast<uint32_t>(nonce[0]) << 24) |
         (static_cast<uint32_t>(nonce[1]) << 16) |
         (static_cast<uint32_t>(nonce[2]) << 8) |
         static_cast<uint32_t>(nonce[3]);
}

static bool
dtDecodeFreshnessBudgetMs(const Interest& interest, uint32_t& fmaxMs)
{
  const uint32_t nonce = dtNonceToUint32(interest);

  if ((nonce & 0xFF000000u) != 0xFD000000u) {
    return false;
  }

  fmaxMs = (nonce >> 12) & 0x0FFFu;
  return true;
}

static uint64_t
dtGetDeliveryGuardUs()
{
  const char* value = std::getenv("DT_STUDY_DELIVERY_GUARD_US");
  if (value == nullptr || value[0] == '\0') return 0;
  try { return static_cast<uint64_t>(std::stoull(value)); }
  catch (...) { return 0; }
}

static bool
dtParseGenerationTimeUs(const Data& data, uint64_t& generationUs)
{
  const ndn::Block& content = data.getContent();
  if (content.value_size() == 0) {
    return false;
  }

  const std::string payload(
    reinterpret_cast<const char*>(content.value()),
    content.value_size());

  if (payload.compare(0, 4, "DT1,") != 0) {
    return false;
  }

  // Payload: DT1,<version>,<generation_us>,<x>,<y>,...
  const size_t versionEnd = payload.find(',', 4);
  if (versionEnd == std::string::npos) {
    return false;
  }

  const size_t generationEnd = payload.find(',', versionEnd + 1);
  if (generationEnd == std::string::npos) {
    return false;
  }

  try {
    generationUs = std::stoull(
      payload.substr(versionEnd + 1, generationEnd - versionEnd - 1));
  }
  catch (...) {
    return false;
  }

  return true;
}

static std::ofstream*
dtGetCacheLog()
{
  static std::ofstream output;
  static bool initialized = false;
  static bool enabled = false;

  if (!initialized) {
    initialized = true;
    const char* path = std::getenv("DT_STUDY_CACHE_CSV");

    if (path != nullptr && path[0] != '\0') {
      output.open(path, std::ios::out | std::ios::trunc);
      enabled = output.is_open();

      if (enabled) {
        output << "time_us,node_context,event,name,nonce,must_be_fresh,"
               << "is_arm_d,fmax_ms,cached_state_age_ms,delivery_guard_ms,"
               << "expected_arrival_age_ms\n";
      }
    }
  }

  return enabled ? &output : nullptr;
}

static void
dtLogCacheEvent(const char* event,
                const Interest& interest,
                bool isArmD,
                uint32_t fmaxMs,
                bool hasAge,
                uint64_t ageUs,
                uint64_t deliveryGuardUs)
{
  std::ofstream* output = dtGetCacheLog();
  if (output == nullptr) {
    return;
  }

  *output << static_cast<uint64_t>(ns3::Simulator::Now().GetMicroSeconds()) << ','
          << ns3::Simulator::GetContext() << ','
          << event << ','
          << '"' << interest.getName().toUri() << '"' << ','
          << dtNonceToUint32(interest) << ','
          << (interest.getMustBeFresh() ? 1 : 0) << ','
          << (isArmD ? 1 : 0) << ',';

  if (isArmD) {
    *output << fmaxMs;
  }
  *output << ',';

  if (hasAge) {
    *output << std::fixed << std::setprecision(3)
            << (static_cast<double>(ageUs) / 1000.0);
  }
  *output << ',';
  if (isArmD) {
    *output << std::fixed << std::setprecision(3)
            << (static_cast<double>(deliveryGuardUs) / 1000.0);
  }
  *output << ',';
  if (hasAge) {
    *output << std::fixed << std::setprecision(3)
            << (static_cast<double>(ageUs + deliveryGuardUs) / 1000.0);
  }
  *output << '\n';
  output->flush();
}
'''

MISS_BODY = r'''

  // DT-STUDY instrumentation: record the real NFD cache miss.
  uint32_t dtFmaxMs = 0;
  const bool dtIsArmD = dtDecodeFreshnessBudgetMs(interest, dtFmaxMs);
  dtLogCacheEvent("MISS", interest, dtIsArmD, dtFmaxMs, false, 0, dtGetDeliveryGuardUs());
'''

HIT_BODY_TEMPLATE = r'''

  // DT-STUDY instrumentation and Arm-D freshness decision.
  uint32_t dtFmaxMs = 0;
  const bool dtIsArmD = dtDecodeFreshnessBudgetMs(interest, dtFmaxMs);

  uint64_t dtGenerationUs = 0;
  const bool dtHasGeneration = dtParseGenerationTimeUs(data, dtGenerationUs);
  const uint64_t dtNowUs =
    static_cast<uint64_t>(ns3::Simulator::Now().GetMicroSeconds());
  const uint64_t dtAgeUs =
    (dtHasGeneration && dtNowUs >= dtGenerationUs)
      ? dtNowUs - dtGenerationUs
      : 0;

  const uint64_t dtDeliveryGuardUs = dtIsArmD ? dtGetDeliveryGuardUs() : 0;
  const uint64_t dtExpectedArrivalAgeUs = dtAgeUs + dtDeliveryGuardUs;

  if (dtIsArmD &&
      dtHasGeneration &&
      dtExpectedArrivalAgeUs > static_cast<uint64_t>(dtFmaxMs) * 1000ULL) {
    NFD_LOG_DEBUG("DT freshness reject interest=" << interest.getName()
                  << " cache-age-us=" << dtAgeUs
                  << " delivery-guard-us=" << dtDeliveryGuardUs
                  << " expected-arrival-age-us=" << dtExpectedArrivalAgeUs
                  << " fmax-ms=" << dtFmaxMs);

    dtLogCacheEvent(
      "STALE_REJECT", interest, true, dtFmaxMs, true, dtAgeUs, dtDeliveryGuardUs);

    // Reuse NFD's normal cache-miss path so PIT bookkeeping and forwarding
    // strategy behavior remain unchanged.
    __MISS_CALL__
    return;
  }

  dtLogCacheEvent(
    "HIT", interest, dtIsArmD, dtFmaxMs, dtHasGeneration, dtAgeUs, dtDeliveryGuardUs);
'''


def target_path(ns3_root: Path) -> Path:
    return ns3_root / "src/ndnSIM/NFD/daemon/fw/forwarder.cpp"


def detect_api(text: str):
    miss_if = MISS_INTEREST_FIRST_RE.search(text)
    hit_if = HIT_INTEREST_FIRST_RE.search(text)
    if miss_if and hit_if:
        return {
            "name": "interest-first",
            "miss_match": miss_if,
            "hit_match": hit_if,
            "miss_call": "this->onContentStoreMiss(interest, ingress, pitEntry);",
        }

    miss_gf = MISS_INGRESS_FIRST_RE.search(text)
    hit_gf = HIT_INGRESS_FIRST_RE.search(text)
    if miss_gf and hit_gf:
        return {
            "name": "ingress-first",
            "miss_match": miss_gf,
            "hit_match": hit_gf,
            "miss_call": "this->onContentStoreMiss(ingress, pitEntry, interest);",
        }

    return None


def insert_after_match(text: str, match: re.Match, body: str) -> str:
    pos = match.end()
    return text[:pos] + body + text[pos:]


def apply_patch(target: Path) -> None:
    backup = Path(str(target) + ".dtstudy.bak")
    text = target.read_text()

    if "dtDecodeFreshnessBudgetMs" in text:
        print("Patch already installed; no changes made.")
        return

    missing = []
    if INCLUDE_ANCHOR not in text:
        missing.append("ndn-cxx include anchor")
    if LOG_ANCHOR not in text:
        missing.append("NFD log anchor")

    api = detect_api(text)
    if api is None:
        missing.append("supported onContentStoreMiss/onContentStoreHit API")

    if missing:
        raise RuntimeError(
            "NFD source does not match a supported Forwarder shape. Missing: "
            + ", ".join(missing)
            + ". Automatic patch aborted without modifying the source."
        )

    if not backup.exists():
        shutil.copy2(target, backup)
        print(f"Backup: {backup}")

    text = text.replace(INCLUDE_ANCHOR, EXTRA_INCLUDES, 1)
    text = text.replace(LOG_ANCHOR, LOG_ANCHOR + HELPERS, 1)

    # Re-detect because the insertions above changed source offsets.
    api = detect_api(text)
    assert api is not None

    text = insert_after_match(text, api["miss_match"], MISS_BODY)

    # Re-detect again because the miss insertion changed the hit offset.
    api = detect_api(text)
    assert api is not None

    hit_body = HIT_BODY_TEMPLATE.replace("__MISS_CALL__", api["miss_call"])
    text = insert_after_match(text, api["hit_match"], hit_body)

    target.write_text(text)

    print(f"Detected NFD API: {api['name']}")
    print(f"Patched: {target}")
    print("Rebuild from the ns-3 root with: ./waf")


def revert_patch(target: Path) -> None:
    backup = Path(str(target) + ".dtstudy.bak")
    if not backup.exists():
        raise RuntimeError(f"Backup not found: {backup}")

    shutil.copy2(backup, target)
    print(f"Restored: {target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ns3_root", help="Path to the ns-3 root")
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Restore forwarder.cpp from the .dtstudy.bak backup",
    )
    args = parser.parse_args()

    ns3_root = Path(args.ns3_root).expanduser().resolve()
    target = target_path(ns3_root)

    if not target.exists():
        raise SystemExit(f"ERROR: {target} not found")

    try:
        if args.revert:
            revert_patch(target)
        else:
            apply_patch(target)
    except RuntimeError as error:
        raise SystemExit(f"ERROR: {error}") from error


if __name__ == "__main__":
    main()
