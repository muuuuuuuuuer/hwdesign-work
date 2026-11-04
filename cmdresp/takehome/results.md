# Part 4 results — Streaming four-tap FIR

## Interface

The 32-bit AXI4-Stream input and output carry one-word headers and separate payload bursts; TKEEP and TSTRB are 0xf. Header fields are opcode [31:24], transaction ID [23:16], and count [15:0]. Signed fixed-point input and output values occupy the low 16 bits. [Specification](prompt.md), [kernel](kernel.cpp).

| Command | Input | Output |
| --- | --- | --- |
| CONFIG (0x01) | Four tap coefficients | None |
| DATA (0x02) | 1–4096 samples | 0x82 header and one filtered sample per consumed input |
| RESET_HISTORY (0x03) | Count 0 | 0x83 header |
| END (0xff) | Count 0 | None; finishes activation |

The `control` AXI-Lite bundle contains only the standard control at 0x00 and 32-bit read-only `halted` at 0x10, `error` at 0x20 and `error_tx_id` at 0x30; see the [generated AXI register map](evidence/run8_register_map.txt) and [RTL testbench](sentinel_tb.v). The input stream has `register_mode=off`, so the AXI input adapter does not accept extra beats after the kernel stops reading. An activation accepts at most 64 non-END commands. The next valid non-END header reports error 7 without accepting its payload; END remains legal after 64. Header errors 1–4 precede this limit check. Payload errors 5 and 6 process the offending DATA sample and halt. [Kernel](kernel.cpp), [prompt](prompt.md).

## Design

CONFIG installs four taps and clears three history samples; RESET_HISTORY clears history; DATA retains history across commands. The dot product uses signed products and a 64-bit accumulator, floor division by 256, and saturation. The Python reference uses independently expressed integer arithmetic. To retain correct history in RTL after Run 6 failed, the DATA loop is unpipelined. This is a deliberate correctness/performance tradeoff: the original II and throughput targets remain unmet rather than being redefined. [Kernel](kernel.cpp), [reference](model.py), [failed pipeline log](evidence/run6_pipeline_cosim_fail.txt).

## Targets

| Criterion | Target | Actual | Verdict | Evidence |
| --- | --- | --- | --- | --- |
| FPGA part | xc7z020clg400-1 | xc7z020clg400-1 | PASS | [run.tcl](run.tcl), [synthesis](evidence/run8_csynth.rpt) |
| Clock | 10 ns constraint; estimate <=10 ns | 10 ns constraint; 6.964 ns estimate | PASS (estimate) | [run.tcl](run.tcl), [synthesis](evidence/run8_csynth.rpt) |
| Stream width | 32 bits each | 32 bits each | PASS | [kernel.hpp](kernel.hpp) |
| Synthesis and RTL co-simulation | Complete | Both completed | PASS | [Vitis log](evidence/run8_vitis.txt), [co-sim report](evidence/run8_cosim.rpt) |
| DATA loop II | <=2 cycles | Unpipelined; report lists no achieved II and iteration latency 8 cycles | FAIL target | [synthesis](evidence/run8_csynth.rpt) |
| DATA throughput | >=0.5 samples/cycle | 0.125000000 samples/cycle | FAIL target | [measurement](evidence/run8_timing_measurements.txt), [waveform](evidence/run8_axis.vcd.gz), [measurement script](measure_rtl.py) |
| First-output latency | Report cycles | 7 cycles | Measured | [measurement](evidence/run8_timing_measurements.txt), [waveform](evidence/run8_axis.vcd.gz) |
| DATA command latency | Report cycles | 32770 cycles | Measured | [measurement](evidence/run8_timing_measurements.txt), [waveform](evidence/run8_axis.vcd.gz) |
| Full 4096-sample activation latency | Report cycles | 32790 cycles | Measured | [timing co-sim](evidence/run8_timing_cosim.rpt) |
| LUT / FF / DSP / BRAM_18K | Report synthesis estimates | 1367 / 953 / 4 / 0 | Reported | [synthesis](evidence/run8_csynth.rpt) |

For the timing fixture, the measured DATA header, first input, first output, and last output occur at cycles 29, 32, 39, and 32799, respectively. A transfer is counted only on a rising edge with TVALID and TREADY high; throughput excludes the response header and equals 4095/(32799−39). [Waveform and numbers](evidence/run8_timing_measurements.txt). These are pre-implementation HLS estimates and RTL simulation measurements, not post-route timing.

## Verification

The following 39 scenarios passed the independent Python reference, host C++ with undefined-behavior sanitizer, Vitis C simulation and RTL co-simulation. Each `_restart` is a separate activation on fresh streams. The testbench compares output words, TLAST, TKEEP, TSTRB, and all status values. [Python](evidence/run8_python.txt), [host C++](evidence/run8_host_cpp.txt), [Vitis C-sim and RTL](evidence/run8_vitis.txt), [co-sim report](evidence/run8_cosim.rpt), [testbench](tb.cpp), [scenarios and hand-checked values](scenarios.py).

Separately, the [directed RTL sentinel test](sentinel_tb.v) presents a stable sentinel immediately after the offending word and records each input handshake through completion; all 16 error scenarios presented it for at least one rising edge and accepted zero, while AXI-Lite status registers matched. [Run 8 sentinel log](evidence/run8_rtl_sentinel.txt). Each test resets the DUT between error scenarios; recovery on a fresh stream is exercised separately by the paired RTL co-simulation scenarios rather than in this sentinel test.

| Scenario | Status (halted, error, tx) | Output beats | Python | Host C++ | Vitis C | RTL |
| --- | --- | ---: | --- | --- | --- | --- |
| `hand_split_reset_reconfigure` | (0, 0, 0) | 14 | PASS | PASS | PASS | PASS |
| `hand_floor_and_upper_bits` | (0, 0, 0) | 5 | PASS | PASS | PASS | PASS |
| `hand_full_accumulator_and_saturation` | (0, 0, 0) | 9 | PASS | PASS | PASS | PASS |
| `activation_state_reset` | (0, 0, 0) | 2 | PASS | PASS | PASS | PASS |
| `seeded_multicommand` | (0, 0, 0) | 514 | PASS | PASS | PASS | PASS |
| `timing_4096` | (0, 0, 0) | 4097 | PASS | PASS | PASS | PASS |
| `command_limit_allows_end` | (0, 0, 0) | 63 | PASS | PASS | PASS | PASS |
| `header_priority` | (1, 1, 21) | 0 | PASS | PASS | PASS | PASS |
| `header_priority_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `unknown_opcode` | (1, 2, 22) | 0 | PASS | PASS | PASS | PASS |
| `unknown_opcode_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `zero_data` | (1, 3, 23) | 0 | PASS | PASS | PASS | PASS |
| `zero_data_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `oversize_data` | (1, 3, 24) | 0 | PASS | PASS | PASS | PASS |
| `oversize_data_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `data_before_config` | (1, 4, 25) | 0 | PASS | PASS | PASS | PASS |
| `data_before_config_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `end_before_config` | (1, 4, 26) | 0 | PASS | PASS | PASS | PASS |
| `end_before_config_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `action_before_config` | (1, 4, 27) | 0 | PASS | PASS | PASS | PASS |
| `action_before_config_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `bad_action_count` | (1, 3, 28) | 0 | PASS | PASS | PASS | PASS |
| `bad_action_count_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `bad_end_count` | (1, 3, 29) | 0 | PASS | PASS | PASS | PASS |
| `bad_end_count_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `bad_config_count` | (1, 3, 30) | 0 | PASS | PASS | PASS | PASS |
| `bad_config_count_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `command_limit` | (1, 7, 42) | 63 | PASS | PASS | PASS | PASS |
| `command_limit_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `command_limit_header_priority` | (1, 1, 43) | 63 | PASS | PASS | PASS | PASS |
| `command_limit_header_priority_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `config_early` | (1, 5, 31) | 0 | PASS | PASS | PASS | PASS |
| `config_early_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `config_missing` | (1, 6, 32) | 0 | PASS | PASS | PASS | PASS |
| `config_missing_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `data_early` | (1, 5, 35) | 5 | PASS | PASS | PASS | PASS |
| `data_early_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |
| `data_missing` | (1, 6, 36) | 2 | PASS | PASS | PASS | PASS |
| `data_missing_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | PASS |

## Assumptions

- Configuration and history are activation-local; a host discards an affected DATA response and resets its stream path before restarting. The kernel does not implement a missing-input timeout. [Prompt](prompt.md).
- The final protocol accepts at most 64 non-END commands per activation; error 7 is enforced after a further valid non-END header. This changes the earlier unlimited draft, and the decision was confirmed after Run 8. [Kernel](kernel.cpp), [boundary tests](test_command_limit.py), [prompt revision](prompt.md#revision-history).
- The 4096-sample timing fixture uses identity coefficients and seeded randomized tests use seed 6463; the hardware remains a programmable four-tap FIR. [Scenarios](scenarios.py).
- The NYU machine lacked a host UBSan runtime, so the sanitizer host run was performed in local WSL; Vitis synthesis and co-simulation ran on ecs03. Account paths in copied logs were redacted as `<EDA-workdir>`.

## Open Items

- Performance target failure is resolved as a documented result, not a passing claim: the current unpipelined design does not meet II <=2 or throughput >=0.5 samples/cycle. A faster correct architecture remains future work. [Synthesis](evidence/run8_csynth.rpt), [measurement](evidence/run8_timing_measurements.txt).
- The 64-command protocol decision is closed in version 4. This documentation-only revision does not claim a new synthesis or RTL co-simulation run; the hardware evidence remains Run 8. [Revision history](prompt.md#revision-history), [Run 8](evidence/run8_vitis.txt).

## Run History

| Run | Prompt version | Action | Result |
| --- | --- | --- | --- |
| 1 | v1 | Model and host C++ | 34/34 passed. [Previous log](evidence/host_cpp.txt) |
| 2–3 | v1 | Vitis C simulation and original unbounded synthesis, including disabled automatic pipelining | C simulation passed; synthesis did not complete. [Run](evidence/synthesis_no_auto_pipeline.txt) |
| 4 | v1 | Minimal probe and FIR synthesis on ecs04 | Probe passed; FIR synthesis timed out (124). [Log](evidence/ecs04_fir_vitis.txt), [status](evidence/ecs04_stage_status.txt) |
| 5 | v1 diagnostic | Disable DATA pipeline in isolated copy, keep unbounded loop | Synthesis timed out (124). [Log](evidence/ecs03_no_data_pipeline_vitis.txt), [status](evidence/ecs03_no_data_pipeline_diagnostic_status.txt) |
| 6 | v2 diagnostic | Bound outer loop to 64 in diagnostic, retain DATA pipeline | Synthesis finished; RTL co-sim failed, 16/34 passing, with incorrect history-dependent outputs. Diagnostic bound silently truncates and is not the final protocol. [Log](evidence/run6_pipeline_cosim_fail.txt) |
| 7 | v3 candidate | Explicit command-limit error and unpipelined DATA; default AXI input registration | Ordinary RTL co-sim passed 39/39, but all 16 directed sentinel cases accepted extra inputs. [Sentinel failure](evidence/run7_rtl_sentinel_fail.txt) |
| 8 | v3 candidate | Disable AXI input registration and rerun full verification | Python, host C++, C-sim, and RTL 39/39; sentinel 16/16; original throughput target fails. [Vitis](evidence/run8_vitis.txt), [sentinel](evidence/run8_rtl_sentinel.txt), [timing](evidence/run8_timing_measurements.txt) |
