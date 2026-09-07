#!/usr/bin/env bash
set -euo pipefail
NS3_ROOT="${1:-$(pwd)}";cd "$NS3_ROOT";rm -rf smoke-v030;./waf
for ARM in A B C D;do echo "=== Smoke $ARM ===";./waf --run="dt-freshness-study --arm=$ARM --experiment=smoke --simulationTime=5 --warmupTime=1 --requestRateHz=10 --requestJitterMs=5 --requestTimeoutMs=80 --freshnessDeliveryGuardMs=2 --fmaxMs=100 --cacheSize=1 --run=1 --outputRoot=smoke-v030";done
echo "=== CSV sizes before analysis ==="
find smoke-v030 -maxdepth 2 -type f \( -name 'requests.csv' -o -name 'offered-requests.csv' -o -name 'timeouts.csv' \) -printf '%10s  %p\n' | sort
python3 dt-study-tools/analyze_results.py smoke-v030
python3 - <<'PYSMOKE'
import pandas as pd
p=pd.read_csv('smoke-v030/pairing-validation.csv');print(p[['arm','approach_name','exact_request_id_match','exact_send_trace_match']].to_string(index=False))
if not ((p.exact_request_id_match==1)&(p.exact_send_trace_match==1)).all():raise SystemExit('ERROR: offered traces differ')
s=pd.read_csv('smoke-v030/summary.csv')
if int(s.n_timeouts.sum())!=0:raise SystemExit(f'ERROR: {int(s.n_timeouts.sum())} timeouts')
print('Smoke validation PASS')
PYSMOKE
