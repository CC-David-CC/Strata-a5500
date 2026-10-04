#include "strata/kernels/readonly_miss_cache.hpp"
#include "strata/kernels/miss_fetch_launch.hpp"

#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace strata::kernels {
namespace {

void check(const char* where) {
    const cudaError_t error = cudaGetLastError();
    if (error != cudaSuccess) {
        std::fprintf(stderr, "%s: %s\n", where, cudaGetErrorString(error));
        std::exit(1);
    }
}

bool compact_miss_fills() {
    static const bool enabled = [] {
        const char* value = std::getenv("STRATA_Q8_COMPACT_MISS_FILL");
        if (!value || std::strcmp(value, "0") == 0) return false;
        if (std::strcmp(value, "1") != 0) {
            std::fprintf(stderr, "STRATA_Q8_COMPACT_MISS_FILL must be 0 or 1\n");
            std::exit(1);
        }
        std::fprintf(stderr, "strata compact miss fill: enabled; visit only upload groups, unchanged bytes and publication\n");
        return true;
    }();
    return enabled;
}

template<bool Compact>
__global__ void plan_kernel(const int32_t* count, const int32_t* starts,
                            const int32_t* dst, const int32_t* ids,
                            uint8_t* staging, int64_t bytes,
                            ReadonlyMissCacheBank bank, ReadonlyMissCachePlan* plan) {
    // Reserve ALL hits before admitting any miss: an early miss must not evict
    // a later member of this same group. Excess misses use ordinary staging.
    bool used[kMissCacheMaxWays] = {};
    const int n = *count;
    plan->count = n;
    if constexpr (Compact) plan->fill_count = 0;
    for (int q = 0; q < n; ++q) {
        const int expert = ids[dst[starts[q]]];
        plan->expert[q] = expert;
        plan->slot[q] = -1;
        plan->fill[q] = 1;
        plan->target[q] = (unsigned long long)(staging + (int64_t)q * bytes);
        for (int s = 0; s < bank.ways; ++s) {
            if (bank.tags[s] != expert) continue;
            used[s] = true;
            plan->slot[q] = s;
            plan->fill[q] = 0;
            plan->target[q] = (unsigned long long)(bank.data + (int64_t)s * bank.stride);
            bank.ages[s] = ++*bank.clock;
            break;
        }
    }
    for (int q = 0; q < n; ++q) {
        if (!plan->fill[q]) continue;
        // Staging bypasses also require a complete upload.
        if constexpr (Compact) plan->fill_groups[plan->fill_count++] = q;
        int victim = -1;
        for (int s = 0; s < bank.ways; ++s) {
            if (used[s]) continue;
            if (bank.tags[s] < 0) { victim = s; break; }
            if (victim < 0 || bank.ages[s] < bank.ages[victim]) victim = s;
        }
        if (victim < 0) continue;
        used[victim] = true;
        plan->slot[q] = victim;
        plan->target[q] = (unsigned long long)(bank.data + (int64_t)victim * bank.stride);
        // Do not publish the new key here. A plan abandoned before its complete
        // copy leaves an invalid slot, not a hit on partially copied weights.
        bank.tags[victim] = -1;
        bank.ages[victim] = ++*bank.clock;
    }
}

template<bool Compact>
__global__ void fill_kernel(const unsigned long long* src, long long per,
                            const ReadonlyMissCachePlan* plan) {
    const long long total = (long long)(Compact ? plan->fill_count : plan->count) * per;
    for (long long i = (long long)blockIdx.x * blockDim.x + threadIdx.x; i < total;
         i += (long long)gridDim.x * blockDim.x) {
        const long long group = i / per, off = i - group * per;
        if constexpr (Compact) {
            const int q = plan->fill_groups[group];
            ((uint4*)plan->target[q])[off] = ((const uint4*)src[q])[off];
        } else if (plan->fill[group]) {
            ((uint4*)plan->target[group])[off] = ((const uint4*)src[group])[off];
        }
    }
}

__global__ void publish_kernel(unsigned long long* ptrs, ReadonlyMissCacheBank bank,
                               const ReadonlyMissCachePlan* plan) {
    // Ordered after the entire fill kernel, not just one block's portion.
    for (int q = 0; q < plan->count; ++q) {
        ptrs[q] = plan->target[q];
        if (plan->fill[q] && plan->slot[q] >= 0)
            bank.tags[plan->slot[q]] = plan->expert[q];
        ++bank.counters[0];
        if (!plan->fill[q]) ++bank.counters[1];
        else ++bank.counters[2];
        if (plan->slot[q] < 0) ++bank.counters[3];
    }
}

}  // namespace

void plan_readonly_misses(const int32_t* count, const int32_t* starts,
                         const int32_t* dst, const int32_t* ids,
                         uint8_t* staging, int64_t bytes, int cap,
                         ReadonlyMissCacheBank bank, ReadonlyMissCachePlan* plan,
                         void* stream) {
    if (cap < 1 || cap > kMissCacheMaxGroups || bank.ways < 1 || bank.ways > kMissCacheMaxWays ||
        bytes <= 0 || bytes > bank.stride || bytes % 16 || bank.stride % 16) {
        std::fprintf(stderr, "readonly miss cache: invalid geometry\n");
        std::exit(1);
    }
    if (compact_miss_fills())
        plan_kernel<true><<<1, 1, 0, (cudaStream_t)stream>>>(count, starts, dst, ids, staging, bytes, bank, plan);
    else
        plan_kernel<false><<<1, 1, 0, (cudaStream_t)stream>>>(count, starts, dst, ids, staging, bytes, bank, plan);
    check("readonly miss cache plan");
}

void fill_readonly_misses(const unsigned long long* src, int64_t bytes,
                         const ReadonlyMissCachePlan* plan, void* stream) {
    if (compact_miss_fills())
        fill_kernel<true><<<miss_fetch_blocks(), 256, 0, (cudaStream_t)stream>>>(src, bytes / 16, plan);
    else
        fill_kernel<false><<<miss_fetch_blocks(), 256, 0, (cudaStream_t)stream>>>(src, bytes / 16, plan);
    check("readonly miss cache fill");
}

void publish_readonly_misses(unsigned long long* ptrs, ReadonlyMissCacheBank bank,
                            const ReadonlyMissCachePlan* plan, void* stream) {
    publish_kernel<<<1, 1, 0, (cudaStream_t)stream>>>(ptrs, bank, plan);
    check("readonly miss cache publish");
}

void fetch_readonly_misses(unsigned long long* ptrs, const int32_t* count,
                          const int32_t* starts, const int32_t* dst,
                          const int32_t* ids, uint8_t* staging, int64_t bytes,
                          int cap, ReadonlyMissCacheBank bank,
                          ReadonlyMissCachePlan* plan, void* stream) {
    plan_readonly_misses(count, starts, dst, ids, staging, bytes, cap, bank, plan, stream);
    fill_readonly_misses(ptrs, bytes, plan, stream);
    publish_readonly_misses(ptrs, bank, plan, stream);
}

}  // namespace strata::kernels
