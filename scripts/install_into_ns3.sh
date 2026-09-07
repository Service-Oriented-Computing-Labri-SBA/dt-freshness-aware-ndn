#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Usage: $0 /path/to/ns-3"; exit 2; fi
NS3_ROOT="$(cd "$1" && pwd)";PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$NS3_ROOT/waf" ]]||{ echo "ERROR: waf not found";exit 1; };[[ -d "$NS3_ROOT/src/ndnSIM" ]]||{ echo "ERROR: ndnSIM not found";exit 1; }
rm -rf "$NS3_ROOT/scratch/dt-study" "$NS3_ROOT/dt-study-src";cp -r "$PKG/dt-study-src" "$NS3_ROOT/dt-study-src";cp "$PKG/scratch/dt-freshness-study.cc" "$NS3_ROOT/scratch/dt-freshness-study.cc";mkdir -p "$NS3_ROOT/dt-study-tools";cp "$PKG/scripts/"*.py "$NS3_ROOT/dt-study-tools/" 2>/dev/null||true;cp "$PKG/scripts/"*.sh "$NS3_ROOT/dt-study-tools/" 2>/dev/null||true;chmod +x "$NS3_ROOT/dt-study-tools/"*.py "$NS3_ROOT/dt-study-tools/"*.sh 2>/dev/null||true;cp "$PKG/requirements.txt" "$NS3_ROOT/dt-study-tools/requirements.txt";echo "Installed DT Freshness Study v0.3.1 into $NS3_ROOT"
