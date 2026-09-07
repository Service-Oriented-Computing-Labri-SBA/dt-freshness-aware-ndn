#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/ns-3" >&2
  exit 2
fi

NS3_ROOT="$(cd "$1" && pwd)"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/5] Checking environment"
bash "$REPO_ROOT/scripts/check_environment.sh" "$NS3_ROOT"

echo "[2/5] Installing experiment"
bash "$REPO_ROOT/scripts/install_into_ns3.sh" "$NS3_ROOT"

echo "[3/5] Applying Arm-D NFD freshness patch"
python3 "$REPO_ROOT/scripts/apply_freshness_patch.py" "$NS3_ROOT"

echo "[4/5] Building ns-3/ndnSIM"
(
  cd "$NS3_ROOT"
  ./waf
)

echo "[5/5] Running smoke validation"
bash "$NS3_ROOT/dt-study-tools/run_smoke_tests.sh" "$NS3_ROOT"
