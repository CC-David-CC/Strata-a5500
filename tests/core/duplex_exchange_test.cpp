#include "strata/core/duplex_exchange.hpp"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

using strata::core::DuplexExchange;
static void check(cudaError_t e) {
    if (e != cudaSuccess) { std::fprintf(stderr, "CUDA: %s\n", cudaGetErrorString(e)); std::exit(1); }
}
static void require(bool ok, const char* what) {
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", what); std::exit(2); }
}
static unsigned char value(size_t i, unsigned seed) {
    return static_cast<unsigned char>((i * 131u + (i >> 8) + seed) & 255u);
}

int main(int argc, char** argv) {
    int devices = 0;
    const cudaError_t device_status = cudaGetDeviceCount(&devices);
    if (device_status != cudaSuccess || !devices) {
        std::fprintf(stderr, "No usable CUDA device: %s (%d devices)\n", cudaGetErrorString(device_status), devices);
        return 77;
    }
    const bool bench = argc == 2 && std::strcmp(argv[1], "--bench") == 0;
    constexpr size_t capacity = 96, largest = 5222400; // real Q8 expert size
    const size_t bytes = capacity * largest;
    unsigned char *incoming = nullptr, *outgoing = nullptr, *scratch = nullptr, *gpu = nullptr;
    check(cudaMallocHost(&incoming, bytes));
    check(cudaMallocHost(&outgoing, bytes));
    check(cudaMallocHost(&scratch, bytes));
    check(cudaMalloc(&gpu, bytes));
    cudaStream_t fill = nullptr;
    check(cudaStreamCreateWithFlags(&fill, cudaStreamNonBlocking));
    DuplexExchange duplex;
    require(duplex.open(0) == cudaErrorInvalidValue, "zero capacity");
    require(duplex.wait_evictions() == cudaErrorInvalidValue, "unopened wait");
    check(duplex.open(capacity));
    require(duplex.open(capacity) == cudaErrorInvalidValue, "double open");
    check(duplex.enqueue(nullptr, 0, fill));
    require(duplex.enqueue(nullptr, 1, fill) == cudaErrorInvalidValue, "null list");
    require(duplex.enqueue(nullptr, capacity + 1, fill) == cudaErrorInvalidValue, "over capacity");
    DuplexExchange::Copy invalid[] = {{gpu, incoming, outgoing, 64}, {gpu + 64, incoming + 64, nullptr, 64}};
    std::memset(outgoing, 0x5a, 128);
    require(duplex.enqueue(invalid, 2, fill) == cudaErrorInvalidValue, "validate whole batch");
    check(duplex.drain());
    require(std::all_of(outgoing, outgoing + 128, [](unsigned char x) { return x == 0x5a; }), "no partial submission");
    invalid[0].bytes = 0;
    require(duplex.enqueue(invalid, 1, fill) == cudaErrorInvalidValue, "empty copy");
    uint64_t expected_copies = 0, expected_payload = 0;
    // Odd byte lengths exercise tails; both model layouts exercise actual DMA sizes.
    for (size_t blob : {size_t(1), size_t(127), size_t(1382400), largest}) {
        for (size_t slots : {size_t(1), size_t(4), size_t(16), capacity}) {
            const size_t n = slots * blob;
            std::vector<DuplexExchange::Copy> copies;
            for (size_t q = 0; q < slots; ++q)
                copies.push_back({gpu + q * blob, incoming + q * blob, outgoing + q * blob, blob});
            for (int rep = 0; rep < (bench ? 8 : 2); ++rep) {
                for (int arm = 0; arm < 2; ++arm) {
                    const bool on = ((rep + arm) & 1) != 0; // balanced AB/BA
                    const unsigned old = 17u + rep * 31u, next = old ^ 0xa5u;
                    for (size_t i = 0; i < n; ++i) {
                        scratch[i] = value(i, old);
                        incoming[i] = value(i, next);
                        outgoing[i] = 0;
                    }
                    check(cudaMemcpyAsync(gpu, scratch, n, cudaMemcpyHostToDevice, fill));
                    check(cudaStreamSynchronize(fill));
                    const auto start = std::chrono::steady_clock::now();
                    if (on) {
                        check(duplex.enqueue(copies.data(), slots, fill));
                        check(duplex.wait_evictions());
                        expected_copies += slots;
                        expected_payload += 2 * n;
                    } else {
                        for (const auto& c : copies)
                            check(cudaMemcpyAsync(c.outgoing, c.slot, c.bytes, cudaMemcpyDeviceToHost, fill));
                        check(cudaStreamSynchronize(fill));
                        for (const auto& c : copies)
                            check(cudaMemcpyAsync(c.slot, c.incoming, c.bytes, cudaMemcpyHostToDevice, fill));
                    }
                    check(cudaStreamSynchronize(fill));
                    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
                    check(cudaMemcpy(scratch, gpu, n, cudaMemcpyDeviceToHost));
                    for (size_t i = 0; i < n; ++i)
                        require(outgoing[i] == value(i, old) && scratch[i] == value(i, next) && incoming[i] == value(i, next),
                                "eviction, refill and immutable source bytes");
                    if (bench)
                        std::printf("{\"blob_bytes\":%zu,\"slots\":%zu,\"rep\":%d,\"duplex\":%s,\"ms\":%.6f,\"payload_bytes\":%zu}\n",
                                    blob, slots, rep, on ? "true" : "false", ms, 2 * n);
                }
            }
        }
    }
    require(duplex.copies() == expected_copies && duplex.payload_bytes() == expected_payload, "byte counters");
    duplex.close();
    duplex.close(); // idempotent and reusable
    // Cancellation/early close: submit real copies, omit both waits, close and
    // immediately inspect/free the buffers. Teardown must finish BOTH directions.
    for (int repeat = 0; repeat < 8; ++repeat) {
        check(duplex.open(1));
        std::memset(scratch, repeat + 1, largest);
        std::memset(incoming, repeat + 17, largest);
        check(cudaMemcpy(gpu, scratch, largest, cudaMemcpyHostToDevice));
        const DuplexExchange::Copy copy{gpu, incoming, outgoing, largest};
        check(duplex.enqueue(&copy, 1, fill));
        duplex.close();
        check(cudaMemcpy(scratch, gpu, largest, cudaMemcpyDeviceToHost));
        for (size_t i = 0; i < largest; ++i)
            require(outgoing[i] == repeat + 1 && scratch[i] == repeat + 17, "close drains both directions");
    }
    check(cudaStreamDestroy(fill));
    check(cudaFree(gpu));
    check(cudaFreeHost(incoming)); check(cudaFreeHost(outgoing)); check(cudaFreeHost(scratch));
    std::puts("duplex exchanges: byte parity, counters, validation and early close passed");
}
