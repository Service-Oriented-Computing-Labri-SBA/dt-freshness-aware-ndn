#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Usage: $0 /path/to/ns-3" >&2; exit 2; fi
NS3_ROOT="$(cd "$1" && pwd)"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORWARDER="$NS3_ROOT/src/ndnSIM/NFD/daemon/fw/forwarder.cpp"
BACKUP="${FORWARDER}.dtstudy.bak"
echo "=== Upgrading to v0.3.1 ==="
if [[ -f "$FORWARDER" ]] && grep -q "dtDecodeFreshnessBudgetMs" "$FORWARDER"; then
  [[ -f "$BACKUP" ]] || { echo "ERROR: missing backup $BACKUP" >&2; exit 1; }
  cp "$BACKUP" "$FORWARDER"
fi
bash "$PKG/scripts/install_into_ns3.sh" "$NS3_ROOT"
python3 "$NS3_ROOT/dt-study-tools/apply_freshness_patch.py" "$NS3_ROOT"
echo "Upgrade complete."
