#pragma once
#include <cstdint>
#include <memory>

namespace strata::prefill::dg_tail {
// Research-only SM120/188-SM adapter. The target weights stay Q8_0; this
// optional down product converts them and the activations to BF16 per call.
class Context {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    bool enabled_ = false;
public:
    Context();
    ~Context();
    bool ready() const;
    bool selected(int type, int experts, int64_t max_rows, int64_t total_rows) const;
    bool run(const void* q8_weights, const float* h, const int32_t counts[4], float* dst, void* stream);
};
}
