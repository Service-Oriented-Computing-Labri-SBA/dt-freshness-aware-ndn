# DT Freshness Study v0.3.1

## Upgrade from v0.3.0

```bash
cd ~/Downloads/dt-freshness-study-v0.3.1
bash scripts/upgrade_to_v031.sh /home/fablab/Desktop/ndnSIM/ns-3
cd /home/fablab/Desktop/ndnSIM/ns-3
./waf
bash dt-study-tools/run_smoke_tests.sh /home/fablab/Desktop/ndnSIM/ns-3
```

The v0.3.0 `EmptyDataError` was caused by at least one short-run CSV still
being buffered when the analyzer opened it. v0.3.1 explicitly flushes the C++
CSV streams and also makes the analyzer safe for a genuine zero-response run.

The final smoke-test line must be:

```text
Smoke validation PASS
```

If it does not pass, inspect:

```bash
find smoke-v030 -maxdepth 2 -type f \
  \( -name 'requests.csv' -o -name 'offered-requests.csv' -o -name 'timeouts.csv' \) \
  -printf '%10s  %p\n' | sort
```

and:

```bash
for d in smoke-v030/*; do
  echo "=== $d ==="
  wc -l "$d/requests.csv" "$d/offered-requests.csv" "$d/timeouts.csv"
done
```

Do not launch the 320-run paper matrix until the smoke test passes.
