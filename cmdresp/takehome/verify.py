"""Independent checks and deterministic vectors for the C++ testbench."""
import hashlib
from pathlib import Path
from typing import NamedTuple

from model import run
from scenarios import cases


class Result(NamedTuple):
    name: str
    words: list
    output: list
    status: tuple


def main():
    results = []
    for name, words, expected, status in cases():
        offered = words + [(0x7edcba98, True)] if status[0] else words
        output, actual_status, consumed = run(offered)
        if (actual_status, consumed) != (status, len(words)):
            raise AssertionError(f"{name}: status/consumed = {actual_status}/{consumed}")
        if expected is not None and output != expected:
            raise AssertionError(f"{name}: output does not match the hand-derived words")
        check = "hand-checked" if expected is not None else "cross-language fixture"
        print(f"MODEL PASS {name}: {check}; status={status}; output_beats={len(output)}")
        results.append(Result(name, words, output, status))

    vector_dir = Path(__file__).resolve().parent / "prj_vectors"
    vector_dir.mkdir(exist_ok=True)
    vectors = vector_dir / "vectors.txt"
    payload = write_vectors(vectors, results)
    print(f"{len(results)} scenarios; vectors SHA256 {hashlib.sha256(payload).hexdigest()}")
    write_vectors(vector_dir / "timing_vectors.txt",
                  [result for result in results if result.name == "timing_4096"])


def write_vectors(path, results):
    if not results:
        raise AssertionError(f"No verification scenarios generated for {path.name}")
    lines = [str(len(results))]
    for name, words, output, (halted, error, tx_id) in results:
        lines.append(f"{name} {len(words)} {len(output)} {halted} {error} {tx_id}")
        lines.extend(f"{data:08x} {int(last)}" for data, last in words + output)
    payload = ("\n".join(lines) + "\n").encode("ascii")
    path.write_bytes(payload)
    return payload


if __name__ == "__main__":
    main()
