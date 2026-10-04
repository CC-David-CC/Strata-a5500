// Raw target-head probabilities. Sampling, penalties and masks never enter this reducer.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace strata::core {
struct TokenProbability { int32_t id = -1; double logprob = 0; };
struct TokenLogprobs {
    TokenProbability selected;
    std::array<TokenProbability, 20> top{};
    int count = 0;
    double proposed = 0;
};

inline TokenLogprobs summarize_logits(const float* logits, int vocab, int selected,
                                     int count, int proposed = -1) {
    if (!logits || vocab < 1 || selected < 0 || selected >= vocab || count < 0 || count > 20 ||
        proposed < -1 || proposed >= vocab)
        throw std::invalid_argument("invalid logprobs dimensions or token ID");
    double peak = -INFINITY;
    TokenLogprobs result;
    result.count = std::min(count, vocab);
    // Stable order for equal logits: smaller token ID first.
    for (int id = 0; id < vocab; ++id) {
        const double value = logits[id];
        if (!std::isfinite(value)) throw std::runtime_error("non-finite raw target logits");
        peak = std::max(peak, value);
        if (!result.count) continue;
        if (result.top[result.count - 1].id >= 0 && value <= result.top[result.count - 1].logprob) continue;
        int slot = result.count - 1;
        while (slot > 0 && (result.top[slot - 1].id < 0 || value > result.top[slot - 1].logprob)) {
            result.top[slot] = result.top[slot - 1]; --slot;
        }
        result.top[slot] = {id, value};
    }
    double sum = 0;
    for (int id = 0; id < vocab; ++id) sum += std::exp(double(logits[id]) - peak);
    const double log_sum = std::log(sum);
    // Subtract peak first: logsumexp rounded at a huge peak would lose the normalizer.
    auto logp = [&](int id) { return (double(logits[id]) - peak) - log_sum; };
    result.selected = {selected, logp(selected)};
    for (int i = 0; i < result.count; ++i) result.top[i].logprob = logp(result.top[i].id);
    if (proposed >= 0) result.proposed = logp(proposed);
    return result;
}
} // namespace strata::core
