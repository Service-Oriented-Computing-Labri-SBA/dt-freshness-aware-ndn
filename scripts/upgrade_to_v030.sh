#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]];then echo "Usage: $0 /path/to/ns-3";exit 2;fi
NS3_ROOT="$(cd "$1"&&pwd)";PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.."&&pwd)";FWD="$NS3_ROOT/src/ndnSIM/NFD/daemon/fw/forwarder.cpp";BAK="${FWD}.dtstudy.bak"
echo "=== Upgrade to DT Freshness Study v0.3.0 ===";if grep -q 'dtDecodeFreshnessBudgetMs' "$FWD";then [[ -f "$BAK" ]]||{ echo "ERROR: backup missing: $BAK";exit 1;};echo "Restoring pristine Forwarder";cp "$BAK" "$FWD";fi;bash "$PKG/scripts/install_into_ns3.sh" "$NS3_ROOT";python3 "$NS3_ROOT/dt-study-tools/apply_freshness_patch.py" "$NS3_ROOT";echo "Upgrade complete. Run: cd $NS3_ROOT && ./waf"
