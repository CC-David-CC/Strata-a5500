#include "strata/core/duplex_exchange.hpp"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static void check(cudaError_t error) {
    if (error != cudaSuccess) {
        std::fprintf(stderr, "CUDA: %s\n", cudaGetErrorString(error));
        std::exit(1);
    }
}

static uint32_t value(size_t i, uint32_t seed) { return uint32_t(i) * 1664525u + seed; }

int main(int argc, char** argv) {
    const bool quick = argc > 1 && std::strcmp(argv[1], "--quick") == 0;
    constexpr size_t blob = 5222400; // actual uniform Q8 expert bytes on this model
    const size_t max_slots = quick ? 16 : 96;
    const size_t bytes = max_slots * blob, words = bytes / sizeof(uint32_t);
    uint32_t *incoming = nullptr, *outgoing = nullptr, *scratch = nullptr;
    uint8_t* gpu = nullptr;
    check(cudaMallocHost(&incoming, bytes));
    check(cudaMallocHost(&outgoing, bytes));
    check(cudaMallocHost(&scratch, bytes));
    check(cudaMalloc(&gpu, bytes));
    cudaStream_t fill = nullptr;
    check(cudaStreamCreateWithFlags(&fill, cudaStreamNonBlocking));
    strata::core::DuplexExchange duplex;
    check(duplex.open(max_slots));
    cudaDeviceProp prop{}; check(cudaGetDeviceProperties(&prop, 0));
    std::printf("{\"gpu\":\"%s\",\"async_engines\":%d,\"blob_bytes\":%zu}\n", prop.name, prop.asyncEngineCount, blob);
    for (size_t slots : {size_t(1), size_t(4), size_t(16), size_t(96)}) {
        if (slots > max_slots) continue;
        const size_t nbytes = slots * blob, nwords = nbytes / sizeof(uint32_t);
        std::vector<strata::core::DuplexExchange::Copy> copies;
        for (size_t i = 0; i < slots; ++i)
            copies.push_back({gpu + i * blob, (uint8_t*)incoming + i * blob,
                              (uint8_t*)outgoing + i * blob, blob});
        const int reps = quick ? 2 : 12;
        for (int rep = 0; rep < reps; ++rep) {
            // Alternating AB/BA, with different contents for every transaction.
            for (int arm = 0; arm < 2; ++arm) {
                const bool use_duplex = ((rep + arm) & 1) != 0;
                const uint32_t old_seed = 17u + uint32_t(rep * 31 + arm);
                const uint32_t new_seed = old_seed ^ 0xa5a55a5au;
                for (size_t i = 0; i < nwords; ++i) {
                    scratch[i] = value(i, old_seed);
                    incoming[i] = value(i, new_seed);
                    outgoing[i] = 0;
                }
                check(cudaMemcpyAsync(gpu, scratch, nbytes, cudaMemcpyHostToDevice, fill));
                check(cudaStreamSynchronize(fill));
                const auto t0 = std::chrono::steady_clock::now();
                if (use_duplex) {
                    check(duplex.enqueue(copies.data(), copies.size(), fill));
                    check(duplex.wait_evictions());
                } else {
                    for (const auto& c : copies)
                        check(cudaMemcpyAsync(c.outgoing, c.slot, c.bytes, cudaMemcpyDeviceToHost, fill));
                    check(cudaStreamSynchronize(fill));
                    for (const auto& c : copies)
                        check(cudaMemcpyAsync(c.slot, c.incoming, c.bytes, cudaMemcpyHostToDevice, fill));
                }
                check(cudaStreamSynchronize(fill));
                const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now()-t0).count();
                // Verify every evicted byte, every incoming GPU byte, and that
                // the source stayed immutable. Verification is outside timing.
                check(cudaMemcpyAsync(scratch, gpu, nbytes, cudaMemcpyDeviceToHost, fill));
                check(cudaStreamSynchronize(fill));
                for (size_t i = 0; i < nwords; ++i) {
                    if (outgoing[i] != value(i, old_seed) || scratch[i] != value(i, new_seed) ||
                        incoming[i] != value(i, new_seed)) {
                        std::fprintf(stderr, "Mismatch at word %zu, slots=%zu rep=%d duplex=%d\n", i, slots, rep, use_duplex);
                        return 2;
                    }
                }
                std::printf("{\"slots\":%zu,\"rep\":%d,\"duplex\":%s,\"milliseconds\":%.9f,\"payload_bytes\":%zu,\"exact\":true}\n",
                            slots, rep, use_duplex ? "true" : "false", ms, 2*nbytes);
                std::fflush(stdout);
            }
        }
    }
    (void)words;
    check(cudaStreamSynchronize(fill)); duplex.close();
    check(cudaStreamDestroy(fill)); check(cudaFree(gpu));
    check(cudaFreeHost(incoming)); check(cudaFreeHost(outgoing)); check(cudaFreeHost(scratch));
    std::puts("{\"completed\":true}");
}
