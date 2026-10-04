#pragma once

#include <chrono>
#include <cstdint>
#include <cstdlib>

namespace strata::program {

struct HostPathTiming {
    bool enabled = [] { const char* v = std::getenv("STRATA_HOST_TIMING"); return v && v[0] == '1'; }();
    double rank = 0, d2h_enqueue = 0, d2h_wait = 0, h2d_enqueue = 0, adapt_total = 0;
    double admission_wait = 0, ownership_commit = 0, table_upload = 0, launch = 0, join = 0;
    uint64_t d2h_bytes = 0, h2d_bytes = 0, swaps = 0;
};

// Each field has one writer at a time. The adaptive task is joined before a
// snapshot or the next admission step. Worker time can overlap GPU execution;
// these buckets must not be summed as independent wall-clock stalls.
class HostPathTimer {
public:
    HostPathTimer(double& total, bool enabled)
        : total_(enabled ? &total : nullptr), start_(enabled ? Clock::now() : Clock::time_point{}) {}
    ~HostPathTimer() {
        if (total_) *total_ += std::chrono::duration<double, std::milli>(Clock::now() - start_).count();
    }
private:
    using Clock = std::chrono::steady_clock;
    double* total_;
    Clock::time_point start_;
};

} // namespace strata::program
