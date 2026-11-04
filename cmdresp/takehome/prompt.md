# Part 3 draft specification — Streaming four-tap FIR

Build a configurable four-tap FIR filter. Write a bit-exact Python golden model, a synthesizable Vitis HLS kernel and a self-checking testbench. Run independent golden-model checks, Vitis C simulation, C synthesis and RTL co-simulation. Compare output words, masks, TLAST and final status bit for bit in both simulations. Keep the logs and reports cited in results.md.

Use the [Waveflow streaming polynomial reference](https://sdrangan.github.io/waveflow/docs/examples/stream_inband/) and the [course command-response pattern](https://sdrangan.github.io/hwdesign/docs/labs/cmdresp/pattern.html). Apply the course pattern for in-band configuration, activation reset and immediate halt on errors. Follow the example's single command loop, separate AXI bursts and golden-model comparison. Use Waveflow MCP to locate the reference.

## Wire protocol

Use one input and one output AXI4-Stream with 32-bit TDATA and TLAST. The host drives TKEEP and TSTRB to 0xf for all input words, and the kernel assumes this. The kernel writes 0xf on both output masks. A header is one word with TLAST=1. Its fields are opcode [31:24], unsigned transaction ID [23:16], and unsigned word count [15:0]. The count in a response is its declared payload length. A nonempty payload is a separate burst with TLAST on its final word. All transaction IDs are legal and may repeat. Responses echo the ID.

The AXI-Lite control bundle uses ap_start/ap_done and unsigned 32-bit outputs `halted`, `error` and `error_tx_id`. Each call starts with all three zero and fresh local state. A valid END returns with zeros. The first command must be CONFIG. After an error, return with halted=1, the code and the offending ID. Read no more input after the offending word or header. The host discards the affected command's response, resets the stream path and starts again with new CONFIG. Completed earlier responses are valid. A source that stops transmitting mid-burst without TLAST can block the kernel while it waits for the next word. No timeout is defined.

| Code | Condition in priority order |
| --- | --- |
| 1 | Header lacks TLAST |
| 2 | Unknown opcode |
| 3 | Header count violates the command table |
| 4 | A syntactically valid non-CONFIG arrives before CONFIG |
| 5 | Payload TLAST occurs before the declared final word |
| 6 | Declared final word has TLAST=0 |
| 7 | A valid non-END header exceeds the per-activation command limit |

The final protocol accepts at most 64 non-END commands per activation (including CONFIG and RESET_HISTORY), and error 7 is normative. After those 64 commands, a valid END still completes successfully. Any other valid command header returns error 7 without consuming that command's payload or emitting its response. Header errors 1–4 retain their listed priority over error 7.

A header error produces no response. A CONFIG payload error produces no response. For DATA, emit the response header before reading the payload. On early or missing TLAST, process the offending sample, mark its output word TLAST=1, then halt. The header still announces the requested count. No footer is sent.

## Commands and data

| Command | Code | Count | Input payload | Output |
| --- | --- | --- | --- | --- |
| CONFIG | 0x01 | 4 | Coefficients c0, c1, c2, c3 | None |
| DATA | 0x02 | 1–4096 | One sample per beat | 0x82 header, then one result per consumed beat |
| RESET_HISTORY | 0x03 | 0 | None | 0x83 header with count=0 |
| END | 0xff | 0 | None | None |

Samples, coefficients and results are signed two's-complement 16-bit values with eight fractional bits. Each payload word puts its value in bits [15:0]. Upper input bits are ignored, upper output bits are zero. Every raw value from -32768 through 32767 is legal. Raw integer r represents r/256.

For the current raw sample x and the three most recent raw samples d1, d2 and d3, compute the exact integer sum A = c0*x + c1*d1 + c2*d2 + c3*d3. Products have 16 fractional bits. Use a signed accumulator wide enough for the full four-product sum, including A=2^32, without intermediate rounding or saturation. Convert once at the end using floor(A/256), including for negative values, then clamp to [-32768, 32767]. Move the raw input into history, dropping the oldest sample. DATA boundaries do not reset history. CONFIG replaces all coefficients and zeroes history. RESET_HISTORY zeroes history and retains the coefficients. No filter state survives the end of an activation.

## Targets and timing

| Criterion | Target |
| --- | --- |
| FPGA part | xc7z020clg400-1 |
| Clock constraint and estimated clock period | 10 ns constraint and estimate <=10 ns |
| AXI TDATA width | 32 bits each direction |
| DATA loop achieved II | <=2 cycles |
| Steady-state output throughput | >=0.5 samples/cycle with the host supplying input and accepting output continuously |

Use a DATA command of 4096 samples (tx_id=0x50) after CONFIG and before END for the timing run. At rising edges in the RTL trace, count transfers only when TVALID and TREADY are both high. Exclude the response header from payload throughput. Report (4096−1)/(last payload transfer cycle−first payload transfer cycle), first-output latency from the first input payload transfer through the first output payload transfer measured as the difference in cycle indices, and command latency from acceptance of the DATA header to the last output payload transfer. Also report the full activation latency from the co-simulation report. Use synthesis for the achieved II, estimated clock, DSP, LUT, FF and BRAM. Record the actual measured values and evidence files or mark a target unverified if the required tool stage cannot run.

If synthesis or RTL co-simulation times out, mark that stage FAIL. Commit the tool log and exit status and identify the last stage that completed. Mark any measurements that depend on the failed stage as unverified and cite that log and status in each affected row. Do not substitute C simulation, the requested II, or results from a different design for FIR hardware measurements.

## Independent verification and test scenarios

Use independent hand calculations for these checks, all in raw units.

- With coefficients [256, 128, -64, 32] and input [256, -256, 512, 0, 0, 0], the expected output is [256, -128, 320, 352, -160, 64]. Split the input across two DATA commands to check history. After RESET_HISTORY, input [256] gives [256]. Reconfigure to [0, 256, 0, 0] and input [256, 0] gives [0, 256].
- With coefficients [1, 0, 0, 0] and input [-1, 1, -257, 257], the expected output is [-1, 0, -2, 1]. With coefficients [-32768, -32768, -32768, -32768] and input [-32768, -32768, -32768, -32768, 32767, 32767, 32767, 32767], expect [32767, 32767, 32767, 32767, 32767, 256, -32768, -32768].
- Cover every command, error code, both DATA length limits, upper-bit handling, and early and missing TLAST on CONFIG and DATA. Test competing header errors to establish priority. For each error, verify status and closure, then run an independent valid CONFIG/DATA/END activation on fresh streams and check the cleared status and output. Include a prior successful response in a DATA framing error test. Verify in C simulation that an extra queued word is left unread.
- For every error scenario, queue a sentinel immediately after the offending beat in a directed RTL test. Present the sentinel at the input and hold its TVALID and payload stable until accepted or the host resets the stream path. From acceptance of the offending beat through activation completion, record the input handshakes and verify that no further beat is accepted. A sentinel handshake is a protocol failure even if the output and status agree with C simulation. Record the sentinel's presentation, any acceptance, completion, status, and fresh-stream restart for each error. If this stimulus or observation cannot be produced, mark the RTL read-ahead check unverified and name the limitation.
- Check the 64-command boundary, error 7 and header-error priority at the boundary. Compare the Python and kernel results on a seeded randomized multicommand activation plus the timing activation.

Write results.md with Interface, Design, Targets, Verification, Assumptions, Open Items and Run History sections. Include one row per scenario and per target, measured values and evidence paths, the actual port/register layout and all decisions made where the prompt was silent. Record any failure and each run's prompt version and scope.

## Revision history

| Version | Change | Why |
| --- | --- | --- |
| 1 | First draft, prepared with Codex | Define a small stateful streaming FIR and its verification contract for student review. |
| 2 (draft at Run 4) | Require an input-handshake trace with a queued sentinel for each RTL error case. Define the verdict and evidence required after a tool timeout. | [Run 4](results.md#run-history) repeated the C-simulation checks, then timed out in synthesis. The co-simulation harness omits queued sentinels, so it would leave read-ahead untested even if ordinary co-simulation passed. [Testbench](tb.cpp), [FIR log](evidence/ecs04_fir_vitis.txt), [exit status](evidence/ecs04_stage_status.txt). |
| 3 (candidate at Run 8) | Bound each activation to 64 non-END commands; define error 7 and its priority. Retain the original performance targets and report their actual verdicts. | The original unbounded command loop did not finish synthesis in earlier runs; Run 6's bounded diagnostic synthesized but pipelined RTL failed 18 scenarios. Run 7 passed ordinary RTL co-simulation with the DATA pipeline disabled but the input adapter accepted queued sentinel words. Run 8 disables input adapter registration and checks both effects. [Run history](results.md#run-history), [pipeline failure](evidence/run6_pipeline_cosim_fail.txt), [read-ahead failure](evidence/run7_rtl_sentinel_fail.txt), [final RTL test](evidence/run8_rtl_sentinel.txt). |
| 4 (final) | 采用用户确认的协议：每次启动最多接受 64 条非 END 命令，其中 CONFIG 和 RESET_HISTORY 也计数；第 65 条合法非 END 命令触发 error 7，64 条之后的 END 仍合法。 | Run 8 implemented and verified the command limit, error status, fresh-stream recovery, and RTL no-read-ahead behavior. This documentation revision accepts that tested behavior; it does not claim a new hardware run. [Vitis log](evidence/run8_vitis.txt), [RTL sentinel log](evidence/run8_rtl_sentinel.txt). |
