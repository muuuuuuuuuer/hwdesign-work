"""Bit-exact transaction model of the four-tap FIR."""


def signed16(word):
    return (word & 0x7fff) - (word & 0x8000)


def run(words):
    """Return output beats, (halted, code, tx_id), and the input beat count."""
    output = []
    cursor = 0
    configured = False
    history = [0, 0, 0]
    command_index = 0

    def read():
        nonlocal cursor
        if cursor == len(words):
            raise ValueError("Input stopped while the accelerator was waiting for a beat")
        word = words[cursor]
        cursor += 1
        return word

    def fail(code, tx):
        return output, (1, code, tx), cursor

    def payload(count):
        for index in range(count):
            word, last = read()
            final = index == count - 1
            frame_error = 0 if last == final else (5 if last else 6)
            yield word, final or bool(frame_error), frame_error
            if frame_error:
                break

    while True:
        header, last = read()
        op, tx, count = header >> 24, (header >> 16) & 255, header & 65535
        if not last:
            return fail(1, tx)
        if op not in (1, 2, 3, 255):
            return fail(2, tx)
        valid_count = 1 <= count <= 4096 if op == 2 else count == (4 if op == 1 else 0)
        if not valid_count:
            return fail(3, tx)
        if not configured and op != 1:
            return fail(4, tx)
        if op == 255:
            return output, (0, 0, 0), cursor
        if command_index == 64:
            return fail(7, tx)
        command_index += 1
        if op == 1:
            values = []
            for word, _, frame_error in payload(count):
                if frame_error:
                    return fail(frame_error, tx)
                values.append(word)
            coefficients = [signed16(word) for word in values]
            history = [0, 0, 0]
            configured = True
        elif op == 3:
            history = [0, 0, 0]
            output.append((0x83000000 | tx << 16, True))
        else:
            output.append((0x82000000 | tx << 16 | count, True))
            for word, final, frame_error in payload(count):
                sample = signed16(word)
                delay = [sample, *history]
                total = sum(c * value for c, value in zip(coefficients, delay))
                value = max(-32768, min(32767, total // 256))
                output.append((value & 0xffff, final))
                history = delay[:3]
                if frame_error:
                    return fail(frame_error, tx)
