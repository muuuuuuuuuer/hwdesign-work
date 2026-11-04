#include "kernel.hpp"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

static AxisWord read_vector_word(std::istream& vectors) {
    uint32_t data;
    unsigned last;
    if (!(vectors >> std::hex >> data >> std::dec >> last) || last > 1) {
        throw std::runtime_error("Invalid vector word");
    }
    AxisWord word;
    word.data = data;
    word.last = last;
    word.keep = word.strb = 0xf;
    return word;
}

int main(int argc, char** argv) {
    const bool rtl = argc > 1 && std::string(argv[argc - 1]) == "--rtl";
    const int path_args = argc - 1 - rtl;
    if (path_args > 1) {
        std::cerr << "Usage: testbench [vectors.txt] [--rtl]\n";
        return 2;
    }
    const char* path = path_args == 1 ? argv[1] : "vectors.txt";
    std::ifstream vectors(path);
    unsigned cases;
    if (!(vectors >> cases) || cases == 0) {
        std::cerr << "Cannot read vectors: " << path << '\n';
        return 2;
    }
    unsigned failed = 0;
    for (unsigned c = 0; c < cases; ++c) {
        std::string name;
        unsigned n_input, n_output;
        uint32_t expected_halted, expected_error, expected_tx;
        if (!(vectors >> name >> n_input >> n_output
                      >> expected_halted >> expected_error >> expected_tx)) {
            throw std::runtime_error("Invalid scenario header");
        }

        hls::stream<AxisWord> in_stream, out_stream;
        for (unsigned i = 0; i < n_input; ++i) {
            in_stream.write(read_vector_word(vectors));
        }
        constexpr uint32_t sentinel = 0x7edcba98;
        const bool check_unread = !rtl && expected_halted;
        if (check_unread) {
            AxisWord word;
            word.data = sentinel;
            word.last = 1;
            word.keep = word.strb = 0xf;
            in_stream.write(word);
        }

        uint32_t halted = 99, error = 99, error_tx = 99;
        fir4(in_stream, out_stream, halted, error, error_tx);
        bool passed = halted == expected_halted && error == expected_error
                   && error_tx == expected_tx;
        for (unsigned i = 0; i < n_output; ++i) {
            const AxisWord expected = read_vector_word(vectors);
            if (out_stream.empty()) {
                passed = false;
                continue;
            }
            const AxisWord actual = out_stream.read();
            if (actual.data != expected.data || actual.last != expected.last
                    || actual.keep != expected.keep || actual.strb != expected.strb) {
                std::cerr << name << ": incorrect output beat " << i << '\n';
                passed = false;
            }
        }
        if (check_unread) {
            const bool unread = !in_stream.empty() && in_stream.read().data == sentinel;
            passed = passed && unread;
        }
        passed = passed && out_stream.empty() && (rtl || in_stream.empty());
        std::cout << (passed ? "KERNEL PASS " : "KERNEL FAIL ") << name
                  << ": status=(" << halted << ',' << error << ',' << error_tx
                  << "); expected_output_beats=" << n_output
                  << "; queued_input_checked=" << check_unread << '\n';
        failed += !passed;
    }
    if (vectors >> std::ws && !vectors.eof()) {
        throw std::runtime_error("Unexpected trailing vector data");
    }
    std::cout << cases - failed << '/' << cases << " scenarios passed\n";
    return failed != 0;
}
