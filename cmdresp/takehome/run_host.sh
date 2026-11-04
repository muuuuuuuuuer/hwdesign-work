#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
mkdir -p prj_host evidence
python3 verify.py | tee evidence/python.txt
"${CXX:-g++}" --version | head -n 1 | tee evidence/host_cpp.txt
"${CXX:-g++}" -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas \
  -fsanitize=undefined -fno-sanitize-recover=undefined -DCMDRESP_HOST_TEST \
  kernel.cpp tb.cpp -o prj_host/tb
./prj_host/tb prj_vectors/vectors.txt | tee -a evidence/host_cpp.txt
