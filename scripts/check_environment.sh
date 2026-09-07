#!/usr/bin/env bash
set -euo pipefail

NS3_ROOT="${1:-/home/fablab/Desktop/ndnSIM/ns-3}"
NS3_ROOT="$(cd "$NS3_ROOT" && pwd)"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ -f "$NS3_ROOT/waf" ]] || fail "waf not found in $NS3_ROOT"
[[ -d "$NS3_ROOT/src/ndnSIM" ]] || fail "src/ndnSIM not found in $NS3_ROOT"

FORWARDER="$NS3_ROOT/src/ndnSIM/NFD/daemon/fw/forwarder.cpp"
[[ -f "$FORWARDER" ]] || fail "NFD forwarder.cpp not found at expected path"

echo "ns-3 root : $NS3_ROOT"
echo "ndnSIM    : $NS3_ROOT/src/ndnSIM"

if git -C "$NS3_ROOT/src/ndnSIM" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  NDN_COMMIT="$(git -C "$NS3_ROOT/src/ndnSIM" rev-parse --short HEAD 2>/dev/null || true)"
  echo "ndnSIM git: $NDN_COMMIT"
  echo "branch    : $(git -C "$NS3_ROOT/src/ndnSIM" branch --show-current 2>/dev/null || true)"

  if [[ "$NDN_COMMIT" == "90d5039" ]]; then
    echo "release   : ndnSIM 2.9 preparation tree (NFD 22.02 / ndn-cxx 0.8.x)"
  fi
fi

INTEREST_HPP="$NS3_ROOT/src/ndnSIM/ndn-cxx/ndn-cxx/interest.hpp"
if [[ -f "$INTEREST_HPP" ]] && grep -q "class Nonce" "$INTEREST_HPP"; then
  echo "Nonce API : Interest::Nonce byte-wrapper"
else
  echo "Nonce API : legacy/scalar or unknown"
fi

if grep -q "Forwarder::onContentStoreHit" "$FORWARDER" && \
   grep -q "Forwarder::onContentStoreMiss" "$FORWARDER"; then
  echo "NFD API   : expected Content Store pipeline found"
else
  fail "expected NFD Content Store hooks were not found"
fi

if grep -q "dtDecodeFreshnessBudgetMs" "$FORWARDER"; then
  echo "DT patch  : installed"
else
  echo "DT patch  : not installed"
fi

echo "scratch   : $(find "$NS3_ROOT/scratch" -maxdepth 1 -name '*.cc' | wc -l) .cc source file(s)"
echo "Environment check passed."
