#include "strata/core/logprobs.hpp"
#include <cassert>
#include <iostream>
#include <limits>
#include <random>
#include <vector>

int main() {
    using strata::core::summarize_logits;
    float basic[] = {0, 0, -2, 1};
    auto s = summarize_logits(basic, 4, 2, 3, 0);
    assert(s.top[0].id == 3 && s.top[1].id == 0 && s.top[2].id == 1);
    assert(std::abs(s.selected.logprob - (-2 - std::log(2 + std::exp(-2.) + std::exp(1.)))) < 1e-14);
    assert(summarize_logits(basic, 4, 3, 0).count == 0);
    float huge[] = {1e30f, 1e30f, -1e30f};
    s = summarize_logits(huge, 3, 2, 20);
    assert(s.count == 3 && std::abs(s.top[0].logprob + std::log(2.)) < 1e-14);
    assert(std::isfinite(s.selected.logprob));
    std::mt19937 rng(675);
    std::normal_distribution<float> dist(0, 10);
    std::vector<float> row(248320);
    for (auto& x : row) x = dist(rng);
    s = summarize_logits(row.data(), (int)row.size(), 117, 20, 654);
    // Independent long-double oracle, directly exponentiating moderate inputs.
    long double denominator = 0;
    for (float x : row) denominator += std::exp((long double)x);
    auto oracle = [&](int id) { return (long double)row[id] - std::log(denominator); };
    assert(std::abs(s.selected.logprob - oracle(117)) < 1e-11);
    assert(std::abs(s.proposed - oracle(654)) < 1e-11);
    for (int i = 0; i < 20; ++i) {
        assert(std::abs(s.top[i].logprob - oracle(s.top[i].id)) < 1e-11);
        if (i) assert(s.top[i-1].logprob >= s.top[i].logprob);
    }
    for (float bad : {INFINITY, -INFINITY, std::numeric_limits<float>::quiet_NaN()}) {
        row[12] = bad;
        bool failed = false;
        try { summarize_logits(row.data(), (int)row.size(), 1, 5); } catch (const std::runtime_error&) { failed = true; }
        assert(failed);
    }
    std::cout << "logprobs: numerical oracle, ties, extremes, selected/proposed outside top-N, non-finite checks passed\n";
}
