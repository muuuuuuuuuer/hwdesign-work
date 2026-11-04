#include "kernel.hpp"

namespace {
constexpr uint32_t CONFIG = 1;
constexpr uint32_t DATA = 2;
constexpr uint32_t ACTION = 3;
constexpr uint32_t END = 255;
constexpr unsigned CONFIG_WORDS = 4;

enum Error : uint32_t {
    OK = 0,
    HEADER_TLAST = 1,
    UNKNOWN_OPCODE = 2,
    BAD_COUNT = 3,
    UNCONFIGURED = 4,
    EARLY_TLAST = 5,
    MISSING_TLAST = 6
};

Error framing(bool last, bool final) {
#pragma HLS INLINE
    if (last == final) {
        return OK;
    }
    return last ? EARLY_TLAST : MISSING_TLAST;
}

void send(hls::stream<AxisWord>& output, uint32_t bits, bool last) {
#pragma HLS INLINE
    AxisWord word;
    word.data = bits;
    word.last = last;
    word.keep = 0xf;
    word.strb = 0xf;
    output.write(word);
}

int16_t signed_sample(uint32_t bits) {
#pragma HLS INLINE
    return static_cast<int16_t>(static_cast<int32_t>(bits & 0x7fff)
                              - static_cast<int32_t>(bits & 0x8000));
}

uint16_t quantize(int64_t sum) {
#pragma HLS INLINE
    // Adding a multiple of 256 makes the shift portable for negative sums.
    constexpr int64_t bias = int64_t{1} << 33;
    const int64_t raw = ((sum + bias) >> 8) - (bias >> 8);
    if (raw > 32767) {
        return 0x7fff;
    }
    if (raw < -32768) {
        return 0x8000;
    }
    return static_cast<uint16_t>(raw);
}
}  // namespace

void fir4(hls::stream<AxisWord>& in_stream, hls::stream<AxisWord>& out_stream,
           uint32_t& halted, uint32_t& error, uint32_t& error_tx_id) {
#pragma HLS INTERFACE axis port=in_stream
#pragma HLS INTERFACE axis port=out_stream
#pragma HLS INTERFACE s_axilite port=halted bundle=control
#pragma HLS INTERFACE s_axilite port=error bundle=control
#pragma HLS INTERFACE s_axilite port=error_tx_id bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    bool configured = false;
    Error code = OK;
    uint32_t tx = 0;
    int16_t coefficients[4] = {};
    int16_t d1 = 0, d2 = 0, d3 = 0;
#pragma HLS ARRAY_PARTITION variable=coefficients complete

    while (true) {
        const AxisWord header = in_stream.read();
        const uint32_t bits = header.data;
        const uint32_t opcode = bits >> 24;
        tx = (bits >> 16) & 0xff;
        const unsigned count = bits & 0xffff;
        const bool valid_count = opcode == DATA ? count >= 1 && count <= 4096
            : count == (opcode == CONFIG ? CONFIG_WORDS : 0);
        if (!header.last) {
            code = HEADER_TLAST;
            break;
        }
        if (opcode != CONFIG && opcode != DATA && opcode != ACTION && opcode != END) {
            code = UNKNOWN_OPCODE;
            break;
        }
        if (!valid_count) {
            code = BAD_COUNT;
            break;
        }
        if (!configured && opcode != CONFIG) {
            code = UNCONFIGURED;
            break;
        }
        if (opcode == END) {
            break;
        }

        if (opcode == CONFIG) {
            for (unsigned i = 0; i < CONFIG_WORDS; ++i) {
                const AxisWord word = in_stream.read();
                code = framing(word.last, i + 1 == CONFIG_WORDS);
                if (code != OK) {
                    break;
                }
                coefficients[i] = signed_sample(word.data);
            }
            if (code != OK) {
                break;
            }
            d1 = d2 = d3 = 0;
            configured = true;
        } else if (opcode == ACTION) {
            d1 = d2 = d3 = 0;
            send(out_stream, 0x83000000u | (tx << 16), true);
        } else {
            send(out_stream, 0x82000000u | (tx << 16) | count, true);
#ifndef CMDRESP_HOST_TEST
        data_samples:
#endif
            for (unsigned i = 0; i < count; ++i) {
#pragma HLS PIPELINE II=2
#pragma HLS LOOP_TRIPCOUNT min=1 max=4096
                const AxisWord word = in_stream.read();
                const bool final = i + 1 == count;
                code = framing(word.last, final);
                const int16_t sample = signed_sample(word.data);
                const int32_t p0 = coefficients[0] * sample;
                const int32_t p1 = coefficients[1] * d1;
                const int32_t p2 = coefficients[2] * d2;
                const int32_t p3 = coefficients[3] * d3;
                const int64_t sum = (int64_t{p0} + p1) + (int64_t{p2} + p3);
                const uint32_t result = quantize(sum);
                d3 = d2;
                d2 = d1;
                d1 = sample;
                send(out_stream, result, final || code != OK);
                if (code != OK) {
                    break;
                }
            }
            if (code != OK) {
                break;
            }
        }
    }

    // Publish the current activation's status when ap_done is asserted.
    halted = code != OK;
    error = code;
    error_tx_id = code != OK ? tx : 0;
}
