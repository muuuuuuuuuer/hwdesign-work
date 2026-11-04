"""Measure the dedicated 4096-sample timing transaction in an XSim VCD."""
import argparse
from bisect import bisect_left

from vcdvcd import VCDVCD


def find_ports(references, requested_scope):
    scopes = {}
    for reference in references:
        scope, _, name = reference.rpartition(".")
        name = name.split("[", 1)[0].lower()
        scopes.setdefault(scope, {})[name] = reference

    required = {"ap_clk"} | {
        f"{stream}_{signal}"
        for stream in ("in_stream", "out_stream")
        for signal in ("tdata", "tlast", "tvalid", "tready")
    }
    candidates = [
        names for scope, names in scopes.items()
        if required <= names.keys() and
        (scope == requested_scope if requested_scope else scope.endswith(".AESL_inst_fir4"))
    ]
    if len(candidates) != 1:
        raise ValueError("Expected one FIR scope with all AXI ports. Use --scope to select it.")
    return {name: candidates[0][name] for name in required}


def value_before(changes, ticks, tick):
    index = bisect_left(ticks, tick) - 1
    return changes[index][1] if index >= 0 else "x"


def transfers(trace, ports, stream, edges):
    signals = {}
    for field in ("tdata", "tlast", "tvalid", "tready"):
        changes = trace[ports[f"{stream}_{field}"]].tv
        signals[field] = (changes, [tick for tick, _ in changes])
    beats = []
    for cycle, tick in enumerate(edges):
        levels = {name: value_before(*values, tick) for name, values in signals.items()}
        if levels["tvalid"] == levels["tready"] == "1":
            beats.append((cycle, int(levels["tdata"], 2), levels["tlast"] == "1"))
    return beats


def payload_after(beats, header):
    starts = [i for i, (_, word, last) in enumerate(beats) if word == header and last]
    if len(starts) != 1:
        raise ValueError(f"Expected exactly one timing header {header:08x}")
    start = starts[0]
    payload = beats[start + 1:start + 4097]
    if len(payload) != 4096 or not payload[-1][2] or any(beat[2] for beat in payload[:-1]):
        raise ValueError(f"Expected a complete 4096-beat burst after header {header:08x}")
    return beats[start][0], payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vcd")
    parser.add_argument("--scope", help="Dotted VCD hierarchy of the FIR DUT")
    args = parser.parse_args()
    ports = find_ports(VCDVCD(args.vcd, only_sigs=True).references_to_ids, args.scope)
    trace = VCDVCD(args.vcd, signals=list(ports.values()))
    edges = [tick for tick, value in trace[ports["ap_clk"]].tv if value == "1"]
    inputs = transfers(trace, ports, "in_stream", edges)
    outputs = transfers(trace, ports, "out_stream", edges)
    header_cycle, data_in = payload_after(inputs, 0x02501000)
    _, data_out = payload_after(outputs, 0x82501000)
    expected = [raw & 0xffff for raw in range(-2048, 2048)]
    if [beat[1] for beat in data_in] != expected or [beat[1] for beat in data_out] != expected:
        raise ValueError("Timing payload words differ from the identity-filter fixture")

    first_input = data_in[0][0]
    first_output, last_output = data_out[0][0], data_out[-1][0]
    if first_output < first_input:
        raise ValueError("Output precedes input. Check the DUT scope and clock.")
    throughput = 4095 / (last_output - first_output)
    print(f"first_output_latency_cycles={first_output - first_input}")
    print(f"data_command_latency_cycles={last_output - header_cycle}")
    print(f"first_output_cycle={first_output}; last_output_cycle={last_output}")
    print(f"throughput_samples_per_cycle={throughput:.9f}")
    print(f"throughput_target={'PASS' if throughput >= 0.5 else 'FAIL'}")
    return int(throughput < 0.5)


if __name__ == "__main__":
    raise SystemExit(main())
