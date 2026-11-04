# Reproducing the FIR results

From this folder on Linux or WSL, run `bash run_host.sh` with Python 3 and g++. This regenerates the vectors and verifies the kernel source with a software stream, a bit-for-bit comparator and UndefinedBehaviorSanitizer.

## Vitis HLS

Use a machine with Vitis HLS and XSim on PATH. On the [NYU EDA servers](https://sdrangan.github.io/hwdesign/docs/support/nyuremote/ssh.html), load the course Xilinx module first.

```bash
module load /home/shared/modules/xilinx
bash run_hls.sh
```

The script runs the independent model checks, vendor C simulation, synthesis, full RTL verification, and a dedicated RTL co-simulation of the 4096-sample timing case. Keep `evidence/vitis.txt` and the copied reports. The generated solution lives under `prj_lab5/`.

## RTL timing

Use the dedicated timing run's XSim snapshot in `prj_lab5/solution1/sim/verilog`. Its name appears in the generated XSim launch command. If a VCD is already available, use it directly. Otherwise run the snapshot with the included [XSim Tcl script](dump_axis.tcl), from the snapshot directory. Replace `SNAPSHOT_NAME` with the name from the generated launch command.

```bash
xsim SNAPSHOT_NAME -tclbatch ../../../../dump_axis.tcl
```

Set `FIR_DUT_SCOPE` to the slash-delimited FIR instance path if auto-discovery fails. From this folder, run the analyzer with the Python `vcdvcd` package available, for example in the course Waveflow environment.

```bash
python3 measure_rtl.py prj_lab5/solution1/sim/verilog/fir4_axis.vcd | tee evidence/rtl_timing.txt
```

The analyzer counts accepted beats at the rising clock edge, confirms the timing payload, and reports latency and throughput. It exits with status 1 if throughput falls below 0.5 samples/cycle. Use `set -o pipefail` before the pipeline to propagate that status. Read full activation latency from `evidence/fir4_timing_cosim.rpt`. Read the clock estimate, the DATA-loop II and resource counts from `evidence/fir4_csynth.rpt`. Update [results.md](results.md) with the real report values and outcome.
