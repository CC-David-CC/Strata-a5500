#pragma once

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cerrno>

#ifdef STRATA_CUDA_DECODE_CAPTURE
#include <cuda_profiler_api.h>
#include <cuda_runtime.h>
#endif

namespace strata::program {

// Diagnostic only: capture complete decode windows after prefill and warmup.
// Disabled unless STRATA_PROFILE_DECODE_COUNT is positive. With capture enabled,
// the two boundary synchronizations and profiler overhead invalidate headline TPS.
// Nsight: --capture-range=cudaProfilerApi --capture-range-end=stop.
// A request ending early (EOS, cancellation, exception) still closes the range.
class DecodeCapture {
public:
    DecodeCapture() {
#ifdef STRATA_CUDA_DECODE_CAPTURE
        count_ = setting("STRATA_PROFILE_DECODE_COUNT", 0);
        skip_ = setting("STRATA_PROFILE_DECODE_SKIP", 16);
#endif
    }
    ~DecodeCapture() { finish(); }
    DecodeCapture(const DecodeCapture&) = delete;
    DecodeCapture& operator=(const DecodeCapture&) = delete;

    void next_window() {
#ifdef STRATA_CUDA_DECODE_CAPTURE
        if (count_ == 0) return;
        if (window_ == skip_ + count_) finish();
        if (window_ == skip_) {
            const cudaError_t sync = cudaDeviceSynchronize();
            const cudaError_t start = sync == cudaSuccess ? cudaProfilerStart() : sync;
            active_ = start == cudaSuccess;
            std::fprintf(stderr, "strata decode capture: start window %lld, count %lld: %s\n",
                         (long long) window_, (long long) count_, cudaGetErrorString(start));
        }
        ++window_;
#endif
    }

    void finish() noexcept {
#ifdef STRATA_CUDA_DECODE_CAPTURE
        if (!active_) return;
        const cudaError_t sync = cudaDeviceSynchronize();
        const cudaError_t stop = cudaProfilerStop();
        std::fprintf(stderr, "strata decode capture: stop after window %lld: sync=%s stop=%s\n",
                     (long long) window_, cudaGetErrorString(sync), cudaGetErrorString(stop));
        active_ = false;
#endif
    }

private:
    static int64_t setting(const char* key, int64_t fallback) {
        const char* text = std::getenv(key);
        if (!text) return fallback;
        char* end = nullptr;
        errno = 0;
        const long long value = std::strtoll(text, &end, 10);
        if (errno || end == text || *end || value < 0 || value > 1000000) {
            std::fprintf(stderr, "strata decode capture: invalid %s; using %lld\n",
                         key, (long long) fallback);
            return fallback;
        }
        return value;
    }
    int64_t window_ = 0, skip_ = 0, count_ = 0;
    bool active_ = false;
};

} // namespace strata::program
