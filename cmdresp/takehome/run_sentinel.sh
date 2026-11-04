#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 write_sentinel_vectors.py
mkdir -p prj_sentinel evidence
cp sentinel_tb.v sentinel_vectors.txt prj_sentinel/
cd prj_sentinel
xvlog -sv ../prj_lab5/solution1/syn/verilog/*.v sentinel_tb.v > compile.log 2>&1
xelab sentinel_tb -s sentinel_sim > elaborate.log 2>&1
xsim sentinel_sim -runall </dev/null > sentinel.log 2>&1
cp sentinel.log ../evidence/rtl_sentinel.txt
grep 'SENTINEL SUMMARY cases=16 failed=0' sentinel.log
if grep -q 'SENTINEL FAIL\|Fatal:' sentinel.log; then exit 1; fi
