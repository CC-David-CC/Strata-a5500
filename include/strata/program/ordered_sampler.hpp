// Experimental full-vocabulary, target-only sampler reference. No model calls,
// GPU resources or persistent RNG state. Existing GPU sampling is unchanged.
#pragma once
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace strata::program::ordered {
struct Options {
    std::vector<std::string> chain;
    std::map<std::string, double> values;
    bool inspect = false;
    bool enabled() const { return !chain.empty() || !values.empty() || inspect; }
    void key(const std::string& k, const std::string& v) {
        if (k == "chain") {
            if (!chain.empty() || v.empty()) throw std::runtime_error("invalid sampler chain");
            size_t at = 0;
            do {
                auto end = v.find(',', at);
                chain.push_back(v.substr(at, end == std::string::npos ? end : end - at));
                if (end == std::string::npos) break;
                at = end + 1;
            } while (at <= v.size());
        } else if (k == "inspect") {
            if (v != "1" || inspect) throw std::runtime_error("invalid sampler inspect");
            inspect = true;
        } else {
            size_t end = 0;
            double number = std::stod(v, &end);
            if (end != v.size() || !std::isfinite(number) || !values.emplace(k, number).second)
                throw std::runtime_error("invalid sampler number");
        }
    }
    void validate() const {
        if (!enabled()) return;
        const std::map<std::string, std::pair<double,double>> ranges{
            {"temperature", {.01,5}}, {"min_p", {0,1}}, {"top_k", {0,300000}},
            {"top_p", {.000001,1}}, {"top_n_sigma", {0,100}},
            {"xtc_probability", {0,1}}, {"xtc_threshold", {.000001,.5}}};
        std::set<std::string> ops(chain.begin(), chain.end()), expected;
        if (chain.empty() || chain.size() > 6 || ops.size() != chain.size() || !ops.count("temperature"))
            throw std::runtime_error("sampler chain requires unique operators and temperature");
        for (const auto& op : chain) {
            if (op == "xtc") { expected.insert("xtc_probability"); expected.insert("xtc_threshold"); }
            else if (op == "temperature" || op == "min_p" || op == "top_k" || op == "top_p" || op == "top_n_sigma")
                expected.insert(op);
            else throw std::runtime_error("unsupported ordered sampler operator");
        }
        if (values.size() != expected.size()) throw std::runtime_error("unused or missing sampler parameter");
        for (const auto& key : expected) {
            auto it = values.find(key);
            if (it == values.end() || !std::isfinite(it->second) || it->second < ranges.at(key).first ||
                it->second > ranges.at(key).second || (key == "top_k" && std::floor(it->second) != it->second))
                throw std::runtime_error("invalid ordered sampler parameter");
        }
    }
};
struct Candidate { int id; double logit; double probability = 0; };
struct Stage { std::string name; size_t support; double entropy; };
struct Decision {
    int id = -1;
    double probability = 0, entropy = 0, milliseconds = 0;
    size_t support = 0;
    std::vector<Stage> stages;
    std::vector<Candidate> top;
    void emit(int64_t index) const {
        std::printf("SP {\"index\":%lld,\"id\":%d,\"probability\":%.17g,\"support\":%zu,\"entropy\":%.17g,"
                    "\"selection_ms\":%.17g,\"stages\":[", (long long)index, id, probability, support, entropy, milliseconds);
        for (size_t i = 0; i < stages.size(); ++i)
            std::printf("%s{\"operator\":\"%s\",\"support\":%zu,\"entropy\":%.17g}", i ? "," : "",
                        stages[i].name.c_str(), stages[i].support, stages[i].entropy);
        std::printf("],\"top\":[");
        for (size_t i = 0; i < top.size(); ++i)
            std::printf("%s{\"id\":%d,\"probability\":%.17g}", i ? "," : "", top[i].id, top[i].probability);
        std::printf("]}\n");
    }
};
inline uint64_t mix(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}
// Named counter lanes keep XTC gates separate from the final categorical draw.
inline double uniform(uint64_t seed, uint64_t position, uint64_t lane) {
    return (mix(seed ^ mix(position) ^ mix(lane)) >> 11) * 0x1.0p-53;
}
inline double normalize(std::vector<Candidate>& c) {
    if (c.empty()) throw std::runtime_error("ordered sampler has no legal candidate");
    double z = 0, entropy = 0;
    for (auto& v : c) { v.probability = std::exp(v.logit - c[0].logit); z += v.probability; }
    for (auto& v : c) {
        v.probability /= z;
        if (v.probability > 0) entropy -= v.probability * std::log(v.probability);
    }
    return entropy;
}
inline Decision select(const float* logits, int nv, const int32_t* mask, const Options& o,
                       uint64_t seed, uint64_t position) {
    const auto start = std::chrono::steady_clock::now();
    o.validate();
    if (!o.enabled() || nv < 1 || nv > 300000 || !logits) throw std::runtime_error("invalid sampler row");
    std::vector<Candidate> c;
    c.reserve(nv);
    for (int id = 0; id < nv; ++id) {
        if (mask && !(uint32_t(mask[id / 32]) & (uint32_t(1) << (id % 32)))) continue;
        if (logits[id] == -INFINITY) continue;
        if (!std::isfinite(logits[id])) throw std::runtime_error("non-finite legal sampler score");
        c.push_back({id, logits[id]});
    }
    std::sort(c.begin(), c.end(), [](const auto& a, const auto& b) {
        return a.logit == b.logit ? a.id < b.id : a.logit > b.logit;
    });
    Decision d;
    auto record = [&](const std::string& name) {
        const double h = normalize(c);
        if (o.inspect) d.stages.push_back({name, c.size(), h});
        return h;
    };
    record("grammar"); // Identity mask when no grammar was requested.
    for (const auto& op : o.chain) {
        if (op == "temperature") {
            for (auto& v : c) v.logit /= o.values.at(op);
        } else if (op == "top_k") {
            const size_t k = (size_t)o.values.at(op);
            if (k && c.size() > k) c.resize(k);
        } else if (op == "min_p" || op == "top_n_sigma") {
            double cut = -INFINITY;
            if (op == "min_p" && o.values.at(op) > 0) cut = c[0].logit + std::log(o.values.at(op));
            if (op == "top_n_sigma" && o.values.at(op) > 0) {
                double mean = 0, m2 = 0, n = 0;
                for (const auto& v : c) { double delta = v.logit - mean; mean += delta / ++n; m2 += delta * (v.logit - mean); }
                cut = c[0].logit - o.values.at(op) * std::sqrt(std::max(0., m2 / n));
            }
            auto end = std::find_if(c.begin() + 1, c.end(), [&](const auto& v) { return v.logit < cut; });
            c.erase(end, c.end());
        } else if (op == "top_p") {
            normalize(c);
            double sum = 0; size_t k = 0;
            do { sum += c[k++].probability; } while (k < c.size() && sum < o.values.at(op));
            c.resize(k);
        } else if (op == "xtc") {
            normalize(c);
            if (uniform(seed, position, 1) < o.values.at("xtc_probability")) {
                size_t k = 0;
                while (k < c.size() && c[k].probability >= o.values.at("xtc_threshold")) ++k;
                if (k > 1) c.erase(c.begin(), c.begin() + k - 1);
            }
        }
        d.entropy = record(op);
    }
    double u = uniform(seed, position, 0), sum = 0;
    size_t selected = c.size() - 1;
    for (size_t i = 0; i < c.size(); ++i) { sum += c[i].probability; if (u < sum) { selected = i; break; } }
    d.id = c[selected].id; d.probability = c[selected].probability; d.support = c.size();
    if (o.inspect) d.top.assign(c.begin(), c.begin() + std::min<size_t>(20, c.size()));
    d.milliseconds = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
    return d;
}
} // namespace strata::program::ordered
