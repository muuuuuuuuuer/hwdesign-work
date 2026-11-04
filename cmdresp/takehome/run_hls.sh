#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if ! command -v vitis-run >/dev/null; then
  echo "Vitis HLS not found. Load the Xilinx module or source its settings64.sh." >&2
  exit 127
fi
mkdir -p evidence
python3 verify.py | tee evidence/python.txt
vitis-run --mode hls --tcl run.tcl 2>&1 | tee evidence/vitis.txt
