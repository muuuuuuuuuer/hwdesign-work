# Reproducing the FIR results

From this folder on Linux or WSL, run `bash run_host.sh` with Python 3 and g++. This regenerates the vectors and verifies the kernel source with a software stream, a bit-for-bit comparator and UndefinedBehaviorSanitizer.

## Vitis HLS

Use a machine with Vitis HLS and XSim on PATH. On the [NYU EDA servers](https://sdrangan.github.io/hwdesign/docs/support/nyuremote/ssh.html), load the course Xilinx module first.

```bash
module load /home/shared/modules/xilinx
bash run_hls.sh
```

The script runs the independent model checks, vendor C simulation, synthesis, full RTL verification, and a dedicated RTL co-simulation of the 4096-sample timing case. Keep `evidence/vitis.txt` and the copied reports. The generated solution lives under `prj_lab5/`. Then run the separate error read-ahead test against the generated Verilog:

```bash
bash run_sentinel.sh
```

It presents a sentinel after each offending word and checks AXI-Lite status and post-error AXI input handshakes. The paired fresh-stream restart scenarios are part of the main RTL co-simulation.

## RTL timing

Use the dedicated timing run's XSim snapshot in `prj_lab5/solution1/sim/verilog`. The commands below use the Vitis 2026.1 generated snapshot and its UVM test name. Use the values in `run_xsim.sh` if another release generates different arguments.

```bash
cd prj_lab5/solution1/sim/verilog
xsim -testplusarg UVM_VERBOSITY=UVM_NONE -testplusarg UVM_TESTNAME=fir4_test_lib -testplusarg UVM_TIMEOUT=20000000000000 fir4 -tclbatch ../../../../dump_axis.tcl </dev/null
cd ../../../..
```

Set `FIR_DUT_SCOPE` to the slash-delimited FIR instance path if the generated hierarchy differs. From this folder, run the analyzer using Python 3; no external Python package is required.

```bash
python3 measure_rtl.py prj_lab5/solution1/sim/verilog/fir4_axis.vcd | tee evidence/rtl_timing.txt
```

The analyzer counts accepted beats at the rising clock edge, confirms the timing payload, and prints the latency, throughput, and target verdict. The analyzer's process exit status indicates whether measurement succeeded; inspect the printed verdict for target failure. Read full activation latency from `evidence/fir4_timing_cosim.rpt`, and read the clock estimate, DATA-loop schedule and resource counts from `evidence/fir4_csynth.rpt`.
