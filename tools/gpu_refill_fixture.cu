#include "strata/core/duplex_exchange.hpp"
#include "strata/core/readonly_cache_snapshot.hpp"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <vector>

static void check(cudaError_t e) {
    if (e != cudaSuccess) {
        std::fprintf(stderr, "CUDA: %s\n", cudaGetErrorString(e));
        std::exit(1);
    }
}
static void require(bool condition, const char* what) {
    if (!condition) { std::fprintf(stderr, "FAIL: %s\n", what); std::exit(2); }
}
static uint32_t word(size_t i, uint32_t seed) { return uint32_t(i)*1664525u + seed; }

int main() {
    using strata::core::DuplexExchange;
    using strata::core::ReadonlyCacheSnapshot;
    constexpr int layers = 3, experts = 512, destinations = 8;
    // Every byte of a real-sized Q8 expert is checked, including its last word.
    constexpr size_t blob = 5222400, words = blob/sizeof(uint32_t);
    size_t cases = 0, d2d_copies = 0, h2d_copies = 0;
    for (int ways : {1, 4, 16}) {
        const size_t slots = layers*ways;
        uint8_t *secondary = nullptr, *primary = nullptr;
        int32_t* device_tags = nullptr;
        uint32_t *scratch = nullptr, *incoming = nullptr, *outgoing = nullptr;
        check(cudaMalloc(&secondary, slots*blob));
        check(cudaMalloc(&primary, destinations*blob));
        check(cudaMalloc(&device_tags, slots*sizeof(int32_t)));
        check(cudaMallocHost(&scratch, destinations*blob));
        check(cudaMallocHost(&incoming, destinations*blob));
        check(cudaMallocHost(&outgoing, destinations*blob));
        cudaStream_t cache_stream = nullptr, fill_stream = nullptr;
        check(cudaStreamCreateWithFlags(&cache_stream, cudaStreamNonBlocking));
        check(cudaStreamCreateWithFlags(&fill_stream, cudaStreamNonBlocking));
        ReadonlyCacheSnapshot snapshot;
        require(snapshot.open(0,experts,ways,blob,device_tags,secondary) == cudaErrorInvalidValue, "zero layers");
        require(snapshot.open(layers,experts,17,blob,device_tags,secondary) == cudaErrorInvalidValue, "ways limit");
        require(snapshot.open(layers,experts,ways,std::numeric_limits<size_t>::max(),device_tags,secondary) ==
            cudaErrorInvalidValue, "stride overflow");
        require(snapshot.open(layers,int64_t(std::numeric_limits<int32_t>::max())+1,ways,blob,device_tags,secondary) ==
            cudaErrorInvalidValue, "tag width overflow");
        check(snapshot.open(layers,experts,ways,blob,device_tags,secondary));
        require(!snapshot.ready() && !snapshot.find(0,0), "no unobserved tag may authorize a read");
        require(!snapshot.complete_after_stream_sync(cudaSuccess), "no fabricated completion");
        DuplexExchange duplex;check(duplex.open(destinations));
        std::vector<int32_t> tags(slots,-1);
        uint32_t* tag_seed = scratch;
        for (size_t slot = 0; slot < slots; ++slot) {
            for (size_t j = 0; j < words; ++j) tag_seed[j] = word(j, uint32_t(1000+slot));
            check(cudaMemcpyAsync(secondary+slot*blob,tag_seed,blob,cudaMemcpyHostToDevice,cache_stream));
            check(cudaStreamSynchronize(cache_stream));
        }
        for (int generation = 0; generation < 4; ++generation) {
            require(snapshot.invalidate(), "prior reads are drained before invalidation");
            require(!snapshot.ready() && !snapshot.find(0,0), "invalidate hides prior tags");
            // Cold, mixed, warm and replaced-tag generations. Contents are
            // immutable; the last generation changes which expert each slot names.
            for (size_t slot = 0; slot < slots; ++slot)
                tags[slot] = generation == 0 || (generation == 1 && slot%2) ? -1 :
                    int32_t(slot%ways + (generation == 3 ? 32 : 0));
            check(cudaMemcpyAsync(device_tags,tags.data(),slots*sizeof(int32_t),cudaMemcpyHostToDevice,cache_stream));
            check(snapshot.enqueue(cache_stream));
            require(!snapshot.ready() && !snapshot.find(0,0), "pending observation hides tags");
            require(!snapshot.invalidate(), "cannot invalidate pending host copy");
            require(snapshot.enqueue(cache_stream) == cudaErrorInvalidValue, "cannot overlap observations");
            require(!snapshot.complete_after_stream_sync(cudaErrorNotReady), "unsuccessful sync does not publish");
            require(snapshot.complete_after_stream_sync(cudaStreamSynchronize(cache_stream)), "publish completed observation");
            require(snapshot.generations() == uint64_t(generation+1), "one generation per completion");
            require(snapshot.bytes() == slots*sizeof(int32_t), "metadata byte accounting");
            require(!snapshot.find(-1,0) && !snapshot.find(layers,0) && !snapshot.find(0,-1) &&
                    !snapshot.find(0,experts), "bounds never expose a pointer");
            for (size_t slot = 0; slot < slots; ++slot) {
                const int expert = int(slot%ways) + (generation == 3 ? 32 : 0);
                require(snapshot.find(slot/ways,expert) == (tags[slot]<0 ? nullptr : secondary+slot*blob),
                        "tag selects exact layer/slot");
            }
            if (generation == 3) require(!snapshot.find(0,0), "replaced expert must miss");
            std::vector<DuplexExchange::Copy> copies;
            std::vector<uint32_t> expected(destinations);
            for (int i = 0; i < destinations; ++i) {
                const int layer = i%layers;
                const int index = i%ways;
                // Some queries deliberately miss even a fully warm cache.
                const int expert = (i%3 == 2 ? 256 : index + (generation == 3 ? 32 : 0));
                const uint8_t* source = snapshot.find(layer,expert);
                const uint32_t seed = source ? uint32_t(1000 + layer*ways + index) : uint32_t(9000+i+generation*20);
                expected[i] = seed;
                for (size_t j = 0; j < words; ++j) {
                    scratch[i*words+j] = word(j,uint32_t(3000+i+generation*20));
                    incoming[i*words+j] = word(j,seed);
                    outgoing[i*words+j] = 0;
                }
                copies.push_back({primary+i*blob,source ? source : (uint8_t*)incoming+i*blob,
                    (uint8_t*)outgoing+i*blob,blob,nullptr,source ? cudaMemcpyDeviceToDevice : cudaMemcpyHostToDevice});
                source ? ++d2d_copies : ++h2d_copies;
            }
            check(cudaMemcpyAsync(primary,scratch,destinations*blob,cudaMemcpyHostToDevice,fill_stream));
            check(cudaStreamSynchronize(fill_stream));
            auto invalid = copies;invalid.back().incoming_kind = cudaMemcpyDeviceToHost;
            require(duplex.enqueue(invalid.data(),invalid.size(),fill_stream) == cudaErrorInvalidValue,
                    "reject whole invalid list before transfers");
            check(duplex.enqueue(copies.data(),copies.size(),fill_stream));
            check(duplex.wait_evictions());
            check(cudaStreamSynchronize(fill_stream)); // immutable source lifetime ends only here
            check(cudaMemcpyAsync(scratch,primary,destinations*blob,cudaMemcpyDeviceToHost,fill_stream));
            check(cudaStreamSynchronize(fill_stream));
            for (int i = 0; i < destinations; ++i)
                for (size_t j = 0; j < words; ++j)
                    require(scratch[i*words+j] == word(j,expected[i]) &&
                            incoming[i*words+j] == word(j,expected[i]) &&
                            outgoing[i*words+j] == word(j,uint32_t(3000+i+generation*20)),
                            "refill, original host source and pre-overwrite victim bytes");
            for (size_t slot = 0; slot < slots; ++slot) {
                check(cudaMemcpyAsync(scratch,secondary+slot*blob,blob,cudaMemcpyDeviceToHost,cache_stream));
                check(cudaStreamSynchronize(cache_stream));
                for (size_t j = 0; j < words; ++j)
                    require(scratch[j] == word(j,uint32_t(1000+slot)), "secondary source remains immutable");
            }
            ++cases;
        }
        require(snapshot.invalidate(), "final invalidate");
        check(snapshot.enqueue(cache_stream));
        snapshot.close(); // owns the unfinished metadata copy, stream still alive
        require(!snapshot.enabled() && !snapshot.ready() && !snapshot.find(0,0), "closed snapshot");
        check(snapshot.open(layers,experts,ways,blob,device_tags,secondary));
        require(snapshot.generations() == 0 && !snapshot.ready(), "fresh reopen has no stale observation");
        snapshot.close();duplex.close();
        check(cudaStreamDestroy(fill_stream));check(cudaStreamDestroy(cache_stream));
        check(cudaFree(device_tags));check(cudaFree(primary));check(cudaFree(secondary));
        check(cudaFreeHost(scratch));check(cudaFreeHost(incoming));check(cudaFreeHost(outgoing));
    }
    require(cases == 12 && d2d_copies > 0 && h2d_copies > 0, "all generations and transfer kinds exercised");
    std::printf("{\"completed\":true,\"cases\":%zu,\"d2d_copies\":%zu,\"h2d_copies\":%zu,"
                "\"blob_bytes\":%zu,\"exact\":true}\n",cases,d2d_copies,h2d_copies,blob);
}
