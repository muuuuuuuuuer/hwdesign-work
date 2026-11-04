# Part 4 results — Streaming four-tap FIR

Both projects follow the [course command-response rules](https://sdrangan.github.io/hwdesign/docs/labs/cmdresp/pattern.html) and the [Waveflow streaming polynomial example](https://sdrangan.github.io/waveflow/docs/examples/stream_inband/).

## Interface

The stream ports are `in_stream` and `out_stream`. The source declares 32-bit TDATA with TLAST and both four-bit masks set to 0xf. Every header is its own TLAST burst. Its opcode is [31:24], transaction ID is [23:16], and declared payload length is [15:0]. Each signed fixed-point payload value occupies [15:0] with eight fractional bits. The kernel ignores input [31:16] and writes output [31:16] as zero.

| Input | Input payload | Output |
| --- | --- | --- |
| CONFIG 0x01, count 4 | c0, c1, c2, c3 | None |
| DATA 0x02, count 1–4096 | One sample per word | 0x82 header with echoed ID and declared count, then one result per consumed sample |
| RESET_HISTORY 0x03, count 0 | None | 0x83 header with echoed ID and count 0 |
| END 0xff, count 0 | None | None |

The top-level AXI-Lite bundle is `control`. It exposes the standard block start/done control and three 32-bit status outputs `halted`, `error` and `error_tx_id`. Read the status for the current activation after completion. The physical register offsets are pending synthesis. Error priorities are header TLAST (1), unknown opcode (2), invalid count (3), absent CONFIG (4), early payload TLAST (5) and missing final payload TLAST (6). Header and CONFIG errors produce no response. A DATA error emits the result for the offending word with TLAST and retains the original declared count in the header. The host discards that response and keeps earlier completed responses.

## Design

CONFIG installs all four taps and clears the three history registers. RESET_HISTORY clears those registers and retains the taps. DATA keeps history across commands. The kernel computes four signed products, adds them in a signed 64-bit accumulator, floors after dividing by 256, and saturates to a signed 16-bit result. The coefficient array is partitioned and the DATA loop requests II=2. The Python model computes the dot product in unbounded integers with Python floor division. The tests independently check the split-burst tap order, reset and reconfiguration, negative fractional rounding, upper bits, and both saturation limits.

## Targets

| Criterion | Required | Measured or declared | Result | Evidence |
| --- | --- | --- | --- | --- |
| FPGA part | xc7z020clg400-1 | xc7z020clg400-1 declared | Configured, build pending | [run.tcl](run.tcl) |
| Clock constraint | 10 ns | 10 ns declared | Configured, build pending | [run.tcl](run.tcl) |
| Stream width | 32 bits per direction | 32 bits in source | PASS at source level | [kernel.hpp](kernel.hpp) |
| C synthesis completion | Finish and generate the FIR synthesis report | 300 s run limit reached | FAIL (timeout) | [ecs04 FIR log](evidence/ecs04_fir_vitis.txt), [exit status](evidence/ecs04_stage_status.txt) |
| Estimated clock period | <=10 ns | Pending | Unverified | Synthesis report required |
| DATA loop achieved II | <=2 cycles | Pending | Unverified | Synthesis report required |
| DATA throughput | >=0.5 samples/cycle | Pending | Unverified | 4096-beat RTL timing trace required |
| First-output and DATA command latency | Report cycles | Pending | Unverified | RTL timing trace required |
| Timing activation latency | Report cycles | Pending | Unverified | Dedicated RTL co-sim report required |
| LUT / FF / DSP / BRAM | Report counts | Pending | Unverified | Synthesis report required |

## Verification

Status tuples show (halted, error, tx_id). `_restart` rows run immediately after the named failure with fresh streams. The Python column includes the independent literals in [scenarios.py](scenarios.py). The seeded randomized case checks agreement between the two implementations. The C++ testbench compares TDATA, TLAST, TKEEP, TSTRB and status for every row. On failure it also checks that a queued sentinel is untouched. The RTL column is pending because FIR synthesis timed out. [Python log](evidence/python.txt), [host C++ log](evidence/host_cpp.txt), [Vitis C simulation log](evidence/vitis_csim.txt), [ecs04 rerun](evidence/ecs04_fir_vitis.txt).

| Scenario | Expected status | Output beats | Python | Host C++ | Vitis C sim | RTL co-sim |
| --- | --- | ---: | --- | --- | --- | --- |
| `hand_split_reset_reconfigure` | (0, 0, 0) | 14 | PASS | PASS | PASS | Pending |
| `hand_floor_and_upper_bits` | (0, 0, 0) | 5 | PASS | PASS | PASS | Pending |
| `hand_full_accumulator_and_saturation` | (0, 0, 0) | 9 | PASS | PASS | PASS | Pending |
| `activation_state_reset` | (0, 0, 0) | 2 | PASS | PASS | PASS | Pending |
| `seeded_multicommand` | (0, 0, 0) | 514 | PASS | PASS | PASS | Pending |
| `timing_4096` | (0, 0, 0) | 4097 | PASS | PASS | PASS | Pending |
| `header_priority` | (1, 1, 21) | 0 | PASS | PASS | PASS | Pending |
| `header_priority_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `unknown_opcode` | (1, 2, 22) | 0 | PASS | PASS | PASS | Pending |
| `unknown_opcode_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `zero_data` | (1, 3, 23) | 0 | PASS | PASS | PASS | Pending |
| `zero_data_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `oversize_data` | (1, 3, 24) | 0 | PASS | PASS | PASS | Pending |
| `oversize_data_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `data_before_config` | (1, 4, 25) | 0 | PASS | PASS | PASS | Pending |
| `data_before_config_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `end_before_config` | (1, 4, 26) | 0 | PASS | PASS | PASS | Pending |
| `end_before_config_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `action_before_config` | (1, 4, 27) | 0 | PASS | PASS | PASS | Pending |
| `action_before_config_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `bad_action_count` | (1, 3, 28) | 0 | PASS | PASS | PASS | Pending |
| `bad_action_count_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `bad_end_count` | (1, 3, 29) | 0 | PASS | PASS | PASS | Pending |
| `bad_end_count_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `bad_config_count` | (1, 3, 30) | 0 | PASS | PASS | PASS | Pending |
| `bad_config_count_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `config_early` | (1, 5, 31) | 0 | PASS | PASS | PASS | Pending |
| `config_early_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `config_missing` | (1, 6, 32) | 0 | PASS | PASS | PASS | Pending |
| `config_missing_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `data_early` | (1, 5, 35) | 5 | PASS | PASS | PASS | Pending |
| `data_early_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |
| `data_missing` | (1, 6, 36) | 2 | PASS | PASS | PASS | Pending |
| `data_missing_restart` | (0, 0, 0) | 3 | PASS | PASS | PASS | Pending |

## Assumptions

- The prompt defines the output, error precedence and reset semantics. A 64-bit accumulator, bias-assisted floor conversion and paired additions are implementation choices.
- Generated stimulus uses seed 6463. The 4096-beat timing fixture is an identity filter with an independently predictable result. The hardware still has four programmable taps.
- The RTL transactor test ends each error stimulus on its offending beat. The C++ test also queues and checks one extra word. RTL read-ahead behavior with queued trailing traffic remains unverified.
- Read the AXI-Lite outputs once the current activation completes. The reported logical reset concerns the new invocation's state.

## Open items

- On ecs03, synthesis stopped making visible progress immediately after the synthesizability check, both with default settings and with automatic loop pipelining disabled. On ecs04, Vitis 2026.1 synthesized the minimal increment probe on the same part at the same 10 ns constraint. FIR C simulation passed 34/34 again, and FIR synthesis timed out at the same stage. The probe confirms the tool can synthesize a minimal design on ecs04. The cause of the FIR stall remains undetermined. The FIR run did not reach RTL co-simulation, so achieved II, clock estimate, resources, latency and throughput remain unverified. The log copies omit the EDA account path. [ecs03 default](evidence/synthesis_default.txt), [ecs03 without automatic pipelining](evidence/synthesis_no_auto_pipeline.txt), [ecs04 probe](evidence/ecs04_probe.txt), [ecs04 FIR](evidence/ecs04_fir_vitis.txt), [exit status](evidence/ecs04_stage_status.txt).
- The student must review the specification, obtain grader feedback and write any revisions. This draft has only the initial version.

## Run history

| Run | Prompt version | What changed | Result |
| --- | --- | --- | --- |
| 1 | Draft v1 | Built Python golden model, HLS source, testbench and replay scripts | Python and host C++ 34/34. |
| 2 | Draft v1 | NYU Vitis 2026.1 after fixing the transfer line endings and vector generation | C simulation 34/34. Synthesis stalled and its process was stopped. |
| 3 | Draft v1 | Disable automatic loop pipelining, retain explicit DATA II=2 | C simulation 34/34. Synthesis stopped producing output at the same stage. |
| 4 | Draft v1 | Run a minimal synthesis probe and rerun the FIR on ecs04 | Probe synthesis passed. FIR C simulation 34/34. FIR synthesis timed out with exit status 124. |
