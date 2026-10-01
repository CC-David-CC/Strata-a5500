#pragma once

// CUDA device intrinsics used by Strata kernels on supported wave32 HIP targets.
// This header is included only from the HIP cuda_runtime compatibility shim.
#if defined(__HIPCC__)

#include <cstdint>

namespace strata::hip_compat {

__device__ __forceinline__ int signed_byte(uint32_t word, int lane) {
    const unsigned value = (word >> (lane * 8)) & 0xffu;
    return value < 0x80u ? static_cast<int>(value) : static_cast<int>(value) - 0x100;
}

// CUDA's signed __dp4a: four signed byte products accumulated modulo 2^32.
__device__ __forceinline__ int dp4a(int a, int b, int c) {
#if (defined(__gfx1100__) || defined(__gfx1101__) || defined(__gfx1102__) || defined(__gfx1200__) || \
     defined(__gfx1201__)) && __has_builtin(__builtin_amdgcn_sudot4)
    // RDNA3 and RDNA4 expose the signed/unsigned dot4 form (v_dot4_i32_iu8). Mark
    // both packed operands signed to preserve CUDA __dp4a semantics; keep the
    // portable path for other HIP compilers/targets.
    return __builtin_amdgcn_sudot4(true, a, true, b, c, false);
#elif defined(__gfx1012__) && !defined(STRATA_GFX1012_PORTABLE_DOT)
    // RDNA1 has no native signed dot4. SDWA selects and sign-extends byte
    // operands directly, avoiding separate shift/mask/sign-extension work.
    // Adapted from pinned llama.cpp ggml-cuda/common.cuh (MIT; see
    // third_party/ggml/LICENSE), same modulo-2^32 accumulation contract.
    int lo, hi;
    asm("v_mul_i32_i24 %1, sext(%3), sext(%4) dst_sel:DWORD dst_unused:UNUSED_PAD src0_sel:BYTE_0 src1_sel:BYTE_0\n"
        "v_mul_i32_i24 %2, sext(%3), sext(%4) dst_sel:DWORD dst_unused:UNUSED_PAD src0_sel:BYTE_1 src1_sel:BYTE_1\n"
        "v_add3_u32 %0, %1, %2, %0\n"
        "v_mul_i32_i24 %1, sext(%3), sext(%4) dst_sel:DWORD dst_unused:UNUSED_PAD src0_sel:BYTE_2 src1_sel:BYTE_2\n"
        "v_mul_i32_i24 %2, sext(%3), sext(%4) dst_sel:DWORD dst_unused:UNUSED_PAD src0_sel:BYTE_3 src1_sel:BYTE_3\n"
        "v_add3_u32 %0, %1, %2, %0\n"
        // c changes before the high-byte reads; it must not alias a or b.
        : "+&v"(c), "=&v"(lo), "=&v"(hi) : "v"(a), "v"(b));
    return c;
#else
    const uint32_t ua = static_cast<uint32_t>(a);
    const uint32_t ub = static_cast<uint32_t>(b);
    uint32_t sum = static_cast<uint32_t>(c);
#pragma unroll
    for (int lane = 0; lane < 4; ++lane)
        sum += static_cast<uint32_t>(signed_byte(ua, lane) * signed_byte(ub, lane));
    return static_cast<int>(sum);
#endif
}

// CUDA's packed byte subtract wraps independently in each unsigned byte lane.
__device__ __forceinline__ int vsub4(int a, int b) {
    const uint32_t ua = static_cast<uint32_t>(a);
    const uint32_t ub = static_cast<uint32_t>(b);
    uint32_t out = 0;
#pragma unroll
    for (int lane = 0; lane < 4; ++lane) {
        const uint32_t x = (ua >> (lane * 8)) & 0xffu;
        const uint32_t y = (ub >> (lane * 8)) & 0xffu;
        out |= ((x - y) & 0xffu) << (lane * 8);
    }
    return static_cast<int>(out);
}

// CUDA's packed signed-byte saturating subtract.
__device__ __forceinline__ int vsubss4(int a, int b) {
    const uint32_t ua = static_cast<uint32_t>(a);
    const uint32_t ub = static_cast<uint32_t>(b);
    uint32_t out = 0;
#pragma unroll
    for (int lane = 0; lane < 4; ++lane) {
        int value = signed_byte(ua, lane) - signed_byte(ub, lane);
        value = value < -128 ? -128 : (value > 127 ? 127 : value);
        out |= (static_cast<uint32_t>(value) & 0xffu) << (lane * 8);
    }
    return static_cast<int>(out);
}

// CUDA's four-lane byte compare, returning 0xff for each unequal lane and 0 otherwise.
__device__ __forceinline__ int vcmpne4(int a, int b) {
    const uint32_t ua = static_cast<uint32_t>(a);
    const uint32_t ub = static_cast<uint32_t>(b);
    uint32_t out = 0;
#pragma unroll
    for (int lane = 0; lane < 4; ++lane) {
        if (((ua >> (lane * 8)) & 0xffu) != ((ub >> (lane * 8)) & 0xffu))
            out |= 0xffu << (lane * 8);
    }
    return static_cast<int>(out);
}

// CUDA's mask argument describes participating lanes. The current kernel set uses full
// wave32 masks; reject future partial-mask use instead of silently dropping its semantics.
__device__ __forceinline__ void require_full_wave_mask(uint32_t mask) {
    if (mask != 0xffffffffu) __builtin_trap();
}

// Older HIP has no __syncwarp. A wave barrier alone does not order memory.
// Release/acquire fences cover the shared-memory exchange used by attention.
__device__ __forceinline__ void syncwarp(uint32_t mask = 0xffffffffu) {
    require_full_wave_mask(mask);
    __builtin_amdgcn_fence(__ATOMIC_RELEASE, "workgroup");
    __builtin_amdgcn_wave_barrier();
    __builtin_amdgcn_fence(__ATOMIC_ACQUIRE, "workgroup");
}

template <typename T>
__device__ __forceinline__ T shfl_xor_sync(uint32_t mask, T value, int lane_mask, int width = 32) {
    require_full_wave_mask(mask);
    return __shfl_xor(value, lane_mask, width);
}

template <typename T>
__device__ __forceinline__ T shfl_down_sync(uint32_t mask, T value, unsigned delta, int width = 32) {
    require_full_wave_mask(mask);
    return __shfl_down(value, delta, width);
}

template <typename T>
__device__ __forceinline__ T shfl_up_sync(uint32_t mask, T value, unsigned delta, int width = 32) {
    require_full_wave_mask(mask);
    return __shfl_up(value, delta, width);
}

template <typename T>
__device__ __forceinline__ T shfl_sync(uint32_t mask, T value, int source_lane, int width = 32) {
    require_full_wave_mask(mask);
    return __shfl(value, source_lane, width);
}

__device__ __forceinline__ unsigned ballot_sync(uint32_t mask, int predicate) {
    require_full_wave_mask(mask);
    return static_cast<unsigned>(__ballot(predicate));
}

}  // namespace strata::hip_compat

#define __dp4a(a, b, c) (::strata::hip_compat::dp4a((a), (b), (c)))
#define __vsub4(a, b) (::strata::hip_compat::vsub4((a), (b)))
#define __vsubss4(a, b) (::strata::hip_compat::vsubss4((a), (b)))
#define __vcmpne4(a, b) (::strata::hip_compat::vcmpne4((a), (b)))
#define __shfl_xor_sync(...) (::strata::hip_compat::shfl_xor_sync(__VA_ARGS__))
#define __shfl_down_sync(...) (::strata::hip_compat::shfl_down_sync(__VA_ARGS__))
#define __shfl_up_sync(...) (::strata::hip_compat::shfl_up_sync(__VA_ARGS__))
#define __shfl_sync(...) (::strata::hip_compat::shfl_sync(__VA_ARGS__))
#define __ballot_sync(mask, predicate) (::strata::hip_compat::ballot_sync((mask), (predicate)))
#define __syncwarp(...) (::strata::hip_compat::syncwarp(__VA_ARGS__))
// AMD's sleep instruction accepts only 0..15; the synchronization loops use it as a
// backoff hint, so use its smallest portable delay independently of CUDA cycle counts.
#define __nanosleep(cycles) __builtin_amdgcn_s_sleep(1)

#endif  // defined(__HIPCC__)
