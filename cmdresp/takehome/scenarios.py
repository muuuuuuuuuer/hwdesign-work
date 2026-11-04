"""Construct protocol words for independent, inspectable verification scenarios."""
import random


def cmd(op, tx, count, last=True):
    return ((op << 24) | (tx << 16) | count, last)


def burst(values):
    return [(value, i == len(values) - 1) for i, value in enumerate(values)]


def data(tx, values):
    return [cmd(2, tx, len(values)), *burst(values)]


def response(tx, values, declared=None):
    count = len(values) if declared is None else declared
    return [cmd(0x82, tx, count), *burst(values)]


def end(tx):
    return cmd(255, tx, 0)


def error_scenarios(cfg, recovery, extra_errors):
    header_errors = [
        ("header_priority", [cmd(0xee, 21, 8, False)], [], (1, 1, 21)),
        ("unknown_opcode", [cmd(0xee, 22, 8)], [], (1, 2, 22)),
        ("zero_data", [cmd(2, 23, 0)], [], (1, 3, 23)),
        ("oversize_data", [cmd(2, 24, 4097)], [], (1, 3, 24)),
        ("data_before_config", [cmd(2, 25, 1)], [], (1, 4, 25)),
        ("end_before_config", [end(26)], [], (1, 4, 26)),
        ("action_before_config", [cmd(3, 27, 0)], [], (1, 4, 27)),
        ("bad_action_count", [*cfg, cmd(3, 28, 1)], [], (1, 3, 28)),
        ("bad_end_count", [*cfg, cmd(255, 29, 1)], [], (1, 3, 29)),
        ("bad_config_count", [cmd(1, 30, 0)], [], (1, 3, 30)),
    ]
    for failure in header_errors + extra_errors:
        yield failure
        yield recovery(failure[0])


def encode(values):
    return [value & 0xffff for value in values]


def config(tx, values):
    return [cmd(1, tx, 4), *burst(encode(values))]


def cases():
    cfg = config(1, [256, 128, -64, 32])
    success = (0, 0, 0)
    yield (
        "hand_split_reset_reconfigure",
        [*cfg, *data(2, encode([256, -256])), *data(3, encode([512, 0, 0, 0])),
         cmd(3, 4, 0), *data(5, [256]), *config(6, [0, 256, 0, 0]),
         *data(7, [256, 0]), end(8)],
        [*response(2, encode([256, -128])), *response(3, encode([320, 352, -160, 64])),
         cmd(0x83, 4, 0), *response(5, [256]), *response(7, [0, 256])],
        success,
    )
    yield (
        "hand_floor_and_upper_bits",
        [cmd(1, 1, 4), *burst([0xbeef0001, 0, 0, 0]),
         *data(2, [0x5a5a0000 | value for value in encode([-1, 1, -257, 257])]), end(3)],
        response(2, encode([-1, 0, -2, 1])), success,
    )
    yield (
        "hand_full_accumulator_and_saturation",
        [*config(1, [-32768] * 4), *data(2, encode([-32768] * 4 + [32767] * 4)),
         end(3)], response(2, encode([32767] * 5 + [256, -32768, -32768])), success,
    )
    yield (
        "activation_state_reset",
        [*cfg, *data(2, [256]), end(3)], response(2, [256]), success,
    )
    rng = random.Random(6463)
    random_data = [rng.getrandbits(32) for _ in range(255)]
    yield (
        "seeded_multicommand",
        [*cfg, *data(0, random_data[:69]), *data(1, random_data[69:]),
         cmd(3, 2, 0), *config(3, [-331, 729, -301, 13]), *data(4, random_data),
         end(0)], None, success,
    )
    timing = encode(list(range(-2048, 2048)))
    yield (
        "timing_4096", [*config(1, [256, 0, 0, 0]), *data(0x50, timing), end(3)],
        response(0x50, timing), success,
    )

    limit_prefix = [*config(1, [256, 0, 0, 0]), *[cmd(3, 2, 0)] * 63]
    limit_responses = [cmd(0x83, 2, 0)] * 63
    yield ("command_limit_allows_end", [*limit_prefix, end(3)], limit_responses, success)

    def recovery(name):
        return (name + "_restart",
                [*config(0xa0, [128, 256, 0, 0]), *data(0xa1, [512, 0]), end(0xa2)],
                response(0xa1, [256, 512]), success)

    extra = [
        ("command_limit", [*limit_prefix, cmd(2, 42, 1)], limit_responses, (1, 7, 42)),
        ("command_limit_header_priority", [*limit_prefix, cmd(0xee, 43, 0, False)],
         limit_responses, (1, 1, 43)),
        ("config_early", [cmd(1, 31, 4), (0, False), (0, True)], [], (1, 5, 31)),
        ("config_missing", [cmd(1, 32, 4), *[(0, False)] * 4], [], (1, 6, 32)),
        ("data_early", [*cfg, *data(2, [256]), cmd(2, 35, 3), (0, False), (256, True)],
         [*response(2, [256]), *response(35, [128, 192], 3)], (1, 5, 35)),
        ("data_missing", [*cfg, cmd(2, 36, 1), (encode([-256])[0], False)],
         response(36, encode([-256])), (1, 6, 36)),
    ]
    yield from error_scenarios(cfg, recovery, extra)
