#pragma once

#include <cstdio>
#include <cstdlib>

namespace strata::kernels {

// Host-side launch configuration, fixed when each CUDA graph is captured.
// Changing the grid changes copy concurrency, never its extent or ownership.
inline int miss_fetch_blocks() {
    static const int blocks = [] {
        const char* value = std::getenv("STRATA_MISS_FETCH_BLOCKS");
        if (value == nullptr) return 48 * 8;
        char* end = nullptr;
        const long parsed = std::strtol(value, &end, 10);
        if (!*value || *end || parsed < 1 || parsed > 4096) {
            std::fprintf(stderr, "STRATA_MISS_FETCH_BLOCKS must be an integer from 1 to 4096\n");
            std::exit(1);
        }
        std::fprintf(stderr, "strata miss fetch geometry: blocks=%ld threads=256; unchanged grid-stride byte copy\n", parsed);
        return (int)parsed;
    }();
    return blocks;
}

}  // namespace strata::kernels
