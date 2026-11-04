#pragma once

#include <cstdint>
#include <queue>
#include <stdexcept>

// Host tests exercise kernel C++ semantics. The Vitis build uses its AXI types.
struct AxisWord {
    uint32_t data = 0;
    bool last = false;
    uint8_t keep = 0;
    uint8_t strb = 0;
};

namespace hls {
template <typename Word>
class stream {
public:
    void write(const Word& word) { words.push(word); }
    bool empty() const { return words.empty(); }

    Word read() {
        if (empty()) {
            throw std::runtime_error("Unexpected read from an empty input stream");
        }
        const Word word = words.front();
        words.pop();
        return word;
    }

private:
    std::queue<Word> words;
};
}  // namespace hls
