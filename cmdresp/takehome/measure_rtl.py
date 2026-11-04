"""Measure timing from a VCD containing the fir4 AXI ports (Python stdlib only)."""
import argparse


def read_transfers(path):
    names = {}
    states = {}
    events = []
    inputs, outputs = [], []
    cycle = -1
    required = {'ap_clk'} | {f'{s}_{p}' for s in ('in_stream', 'out_stream')
                             for p in ('tdata', 'tlast', 'tvalid', 'tready')}

    def process():
        nonlocal cycle
        if any(names.get(key) == 'ap_clk' and val == '1' for key, val in events):
            cycle += 1
            for stream, beats in (('in_stream', inputs), ('out_stream', outputs)):
                if states.get(stream + '_tvalid') == states.get(stream + '_tready') == '1':
                    data = states[stream + '_tdata']
                    if any(c not in '01' for c in data):
                        raise ValueError('Unknown data during an AXI transfer')
                    beats.append((cycle, int(data, 2), states[stream + '_tlast'] == '1'))
        for key, value in events:
            if key in names:
                states[names[key]] = value
        events.clear()

    with open(path, encoding='ascii') as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            if parts[0] == '$var':
                name = parts[4].lower()
                if name in required:
                    if name in names.values():
                        raise ValueError('Duplicate selected signal: ' + name)
                    names[parts[3]] = name
            elif line.startswith('#'):
                process()
            elif line[0] in '01xXzZ' and len(parts[0]) >= 2:
                events.append((parts[0][1:], parts[0][0].lower()))
            elif line[0] in 'bB' and len(parts) == 2:
                events.append((parts[1], parts[0][1:].lower()))
    process()
    if set(names.values()) != required:
        raise ValueError(f'Missing signals: {required - set(names.values())}')
    return inputs, outputs


def payload_after(beats, header):
    starts = [i for i, (_, word, last) in enumerate(beats) if word == header and last]
    if len(starts) != 1:
        raise ValueError(f'Expected exactly one header {header:08x}, found {len(starts)}')
    start = starts[0]
    payload = beats[start + 1:start + 4097]
    if len(payload) != 4096 or not payload[-1][2] or any(x[2] for x in payload[:-1]):
        raise ValueError('Incomplete 4096-beat payload')
    return beats[start][0], payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vcd')
    args = parser.parse_args()
    inputs, outputs = read_transfers(args.vcd)
    header, data_in = payload_after(inputs, 0x02501000)
    _, data_out = payload_after(outputs, 0x82501000)
    expected = [raw & 0xffff for raw in range(-2048, 2048)]
    if [x[1] for x in data_in] != expected or [x[1] for x in data_out] != expected:
        raise ValueError('Timing payload data do not match the identity filter fixture')
    first_input, first_output, last_output = data_in[0][0], data_out[0][0], data_out[-1][0]
    if first_output < first_input:
        raise ValueError('Output precedes input')
    throughput = 4095 / (last_output - first_output)
    print(f'input_header_cycle={header}; first_input_cycle={first_input}')
    print(f'first_output_cycle={first_output}; last_output_cycle={last_output}')
    print(f'first_output_latency_cycles={first_output - first_input}')
    print(f'data_command_latency_cycles={last_output - header}')
    print(f'throughput_samples_per_cycle={throughput:.9f}')
    print(f'throughput_target={"PASS" if throughput >= 0.5 else "FAIL"}')


if __name__ == '__main__':
    main()
