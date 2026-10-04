// Server-owned, opt-in evidence. Neither path is accepted from an HTTP request.
#pragma once
#include "strata/core/logprobs.hpp"
#include <cstdio>
#include <cstdlib>
#include <stdexcept>

namespace strata::program {
class LogprobDiagnostics {
    const char *trace_, *raw_;
    std::FILE *trace_file_ = nullptr, *raw_file_ = nullptr;
    uint64_t request_, raw_rows_ = 0, raw_dropped_ = 0, copied_rows_ = 0, bytes_ = 0;
    double score_ms_ = 0;
    static uint64_t next_request() { static uint64_t n = 0; return ++n; }
    static std::FILE* open(const char* path, std::FILE*& file) {
        if (!file && !(file = std::fopen(path, "ab"))) throw std::runtime_error("cannot open logprobs evidence path");
        return file;
    }
public:
    explicit LogprobDiagnostics(bool scoring)
        : trace_(scoring ? std::getenv("STRATA_LOGPROBS_TRACE") : nullptr),
          raw_(scoring ? std::getenv("STRATA_LOGPROBS_RAW") : nullptr), request_(next_request()) {}
    ~LogprobDiagnostics() {
        if (trace_file_) std::fclose(trace_file_);
        if (raw_file_) std::fclose(raw_file_);
    }
    bool enabled() const { return trace_ || raw_; }

    void raw_row(int window, int row, int rows, int retained, int64_t position, int selected,
                 int proposed, const float* values, int vocab) {
        if (!raw_) return;
        // Raw tensors are an explicitly bounded numerical fixture, not a log of every token.
        if (raw_rows_ >= 32) { ++raw_dropped_; return; }
        auto* f = open(raw_, raw_file_);
        if (std::fprintf(f, "LPRAW1 %llu %d %d %d %d %lld %d %d %d\n", (unsigned long long)request_,
                         window, row, rows, retained, (long long)position, selected, proposed, vocab) < 0 ||
            std::fwrite(values, sizeof(float), vocab, f) != (size_t)vocab || std::fputc('\n', f) == EOF)
            throw std::runtime_error("cannot write logprobs raw evidence");
        ++raw_rows_;
    }

    void window(int window, int64_t position, int rows, int proposed_rows, int retained,
                const int32_t* inputs, const core::TokenLogprobs* scores, bool suffix,
                const float* draft_probs, bool coupled, int draft_vocab, int target_vocab, bool proposal_eos, double ms) {
        copied_rows_ += rows; bytes_ += uint64_t(rows) * target_vocab * sizeof(float); score_ms_ += ms;
        if (!trace_) return;
        auto* f = open(trace_, trace_file_);
        std::fprintf(f, "{\"type\":\"verification\",\"request\":%llu,\"window\":%d,\"position\":%lld,"
                        "\"proposal_source\":\"%s\",\"probability_source\":\"target_raw_full_vocabulary\","
                        "\"target_vocab\":%d,\"scored_length\":%d,\"proposed_length\":%d,"
                        "\"complete\":%s,\"retained_outputs\":%d,\"accepted_proposals\":%d,"
                        "\"termination_included\":%s,\"proposal\":[",
                     (unsigned long long)request_, window, (long long)position, suffix ? "suffix" : rows > 1 ? "mtp" : "none",
                     target_vocab, rows - 1, proposed_rows - 1, rows == proposed_rows ? "true" : "false", retained, retained - 1,
                     proposal_eos ? "true" : "false");
        double sum = 0;
        for (int i = 0; i + 1 < rows; ++i) {
            sum += scores[i].proposed;
            std::fprintf(f, "%s{\"token_id\":%d,\"target_logprob\":%.17g", i ? "," : "", inputs[i + 1], scores[i].proposed);
            if (!suffix) {
                // Existing MTP probabilities are float scalars. A zero may be underflow, never invent a finite logp.
                std::fprintf(f, ",\"draft_distribution\":\"%s\",\"draft_vocab\":%d,\"draft_probability\":%.9g,\"draft_logprob\":",
                    coupled ? "post_sampling_chain" : "raw_draft_vocabulary", draft_vocab, draft_probs[i]);
                if (draft_probs[i] > 0 && std::isfinite(draft_probs[i])) std::fprintf(f, "%.17g", std::log(double(draft_probs[i])));
                else std::fprintf(f, "null");
            }
            std::fprintf(f, "}");
        }
        std::fprintf(f, "],\"target_sequence_logprob\":%.17g,\"emitted\":[", sum);
        for (int i = 0; i < retained; ++i)
            std::fprintf(f, "%s{\"token_id\":%d,\"logprob\":%.17g}", i ? "," : "", scores[i].selected.id, scores[i].selected.logprob);
        if (std::fprintf(f, "]}\n") < 0 || std::ferror(f)) throw std::runtime_error("cannot write logprobs trace");
    }

    void finish() {
        if (trace_) {
            auto* f = open(trace_, trace_file_);
            if (std::fprintf(f, "{\"type\":\"score_cost\",\"request\":%llu,\"copied_rows\":%llu,\"device_to_host_bytes\":%llu,"
                               "\"copy_and_reduce_ms\":%.6f,\"raw_rows\":%llu,\"raw_dropped\":%llu}\n",
                (unsigned long long)request_, (unsigned long long)copied_rows_, (unsigned long long)bytes_, score_ms_,
                (unsigned long long)raw_rows_, (unsigned long long)raw_dropped_) < 0 || std::fflush(f) != 0)
                throw std::runtime_error("cannot finish logprobs trace");
        }
        if (raw_file_ && std::fflush(raw_file_) != 0) throw std::runtime_error("cannot finish raw logprobs evidence");
    }
};
} // namespace strata::program
