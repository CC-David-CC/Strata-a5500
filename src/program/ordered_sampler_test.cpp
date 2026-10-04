// Analytical synthetic fixtures, not a model quality benchmark.
#include "strata/program/ordered_sampler.hpp"
#include <cassert>
#include <iostream>
#include <limits>
using namespace strata::program::ordered;

Options profile(std::vector<std::string> chain, std::map<std::string,double> values) {
    Options o; o.chain = std::move(chain); o.values = std::move(values); o.inspect = true; return o;
}
template<class F> void fails(F f) { bool threw = false; try { f(); } catch (const std::exception&) { threw = true; } assert(threw); }
int main() {
    auto temperature = profile({"temperature"}, {{"temperature",1}});
    float row[] = {std::log(.6f), std::log(.3f), std::log(.1f)};
    auto d = select(row, 3, nullptr, temperature, 675, 0);
    assert(d.support == 3 && d.top[0].id == 0);
    assert(std::abs(d.top[0].probability - .6) < 1e-7);
    auto hot = temperature; hot.values["temperature"] = 2;
    auto h = select(row, 3, nullptr, hot, 675, 0);
    assert(std::abs(h.top[0].probability - std::sqrt(.6)/(std::sqrt(.6)+std::sqrt(.3)+std::sqrt(.1))) < 1e-7);
    assert(h.entropy > d.entropy);
    auto minp = profile({"min_p","temperature"}, {{"min_p",.3},{"temperature",2}});
    assert(select(row, 3, nullptr, minp, 1, 0).support == 2);
    minp.chain = {"temperature","min_p"};
    assert(select(row, 3, nullptr, minp, 1, 0).support == 3); // order changes support
    auto sigma = profile({"top_n_sigma","temperature"}, {{"top_n_sigma",1},{"temperature",1.5}});
    float sr[] = {4,3,0,-1}; // mean 1.5; std sqrt(4.25); threshold ~1.938
    assert(select(sr, 4, nullptr, sigma, 5, 0).support == 2);
    sigma.chain = {"temperature","top_n_sigma"};
    assert(select(sr, 4, nullptr, sigma, 5, 0).support == 2); // positive scaling leaves sigma support invariant
    auto xtc = profile({"xtc","temperature"}, {{"xtc_probability",1},{"xtc_threshold",.2},{"temperature",1}});
    d = select(row, 3, nullptr, xtc, 2, 0);
    assert(d.support == 2 && d.top[0].id == 1 && std::abs(d.top[0].probability - .75) < 1e-7);
    xtc.values["xtc_threshold"] = .4;
    assert(select(row, 3, nullptr, xtc, 2, 0).support == 3); // only one above threshold: no removal
    xtc.values["xtc_probability"] = 0;
    assert(select(row, 3, nullptr, xtc, 2, 0).support == 3);
    auto kp = profile({"top_k","top_p","temperature"}, {{"top_k",2},{"top_p",.5},{"temperature",1}});
    assert(select(row, 3, nullptr, kp, 2, 0).support == 1);
    std::vector<float> flat(1000, 0);
    auto all = select(flat.data(), 1000, nullptr, temperature, 1, 0);
    assert(all.support == 1000 && std::abs(all.entropy - std::log(1000)) < 1e-10);
    assert(all.top[19].id == 19); // no inherited top-64 cap
    int32_t mask[] = {int32_t(uint32_t(1) << 31), 1};
    auto masked = select(flat.data(), 33, mask, temperature, 1, 0);
    assert(masked.support == 2 && masked.top[0].id == 31 && masked.top[1].id == 32);
    int32_t zero = 0, only = 2;
    fails([&] { select(row, 3, &zero, temperature, 1, 0); });
    assert(select(row, 3, &only, xtc, 1, 0).id == 1);
    float bad[] = {std::numeric_limits<float>::quiet_NaN(), 0};
    fails([&] { select(bad, 2, nullptr, temperature, 1, 0); });
    assert(select(bad, 2, &only, temperature, 1, 0).id == 1); // masked NaN never eligible
    bad[0] = -INFINITY;
    assert(select(bad, 2, nullptr, temperature, 1, 0).id == 1);
    auto invalid = temperature; invalid.chain.push_back("temperature");
    fails([&] { invalid.validate(); });
    invalid = temperature; invalid.values["min_p"] = .1;
    fails([&] { invalid.validate(); });
    Options parsed; parsed.key("chain","min_p,temperature"); parsed.key("min_p",".05"); parsed.key("temperature","1.5"); parsed.validate();
    fails([&] { parsed.key("temperature","1.0"); });
    fails([&] { Options o; o.key("temperature","1garbage"); });
    // RNG: same row/seed/position repeats; positions need no mutable RNG state.
    int counts[3] = {};
    for (uint64_t i = 0; i < 20000; ++i) {
        auto v = select(row, 3, nullptr, temperature, 675, i);
        assert(v.id == select(row, 3, nullptr, temperature, 675, i).id);
        counts[v.id]++;
    }
    assert(std::abs(counts[0]/20000. - .6) < .02 && std::abs(counts[1]/20000. - .3) < .02);
    std::cout << "PASS ordered sampler: analytical probabilities, operator order, full vocabulary, masks, XTC, sigma, validation, counter RNG (20000 draws)\n";
}
