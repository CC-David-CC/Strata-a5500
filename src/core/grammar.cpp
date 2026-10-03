#include "strata/core/grammar.hpp"
#include "strata/core/grammar_budget.hpp"

#include <xgrammar/config.h>
#include <xgrammar/xgrammar.h>

#include <algorithm>
#include <chrono>
#include <iomanip>
#include <list>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace strata::grammar {
using namespace std::chrono_literals;

static std::string source_identity(const std::string& source) {
    uint64_t h = 14695981039346656037ull;
    for (unsigned char byte : source) h = (h ^ byte) * 1099511628211ull;
    std::ostringstream out;
    out << "root-gbnf-v1-fnv1a64:" << std::hex << std::setfill('0') << std::setw(16) << h;
    return out.str(); // diagnostic only; cache and checkpoints also compare actual ownership/source
}

bool valid_utf8(const std::string& s) {
    for (size_t i = 0; i < s.size();) {
        uint32_t c = (uint8_t) s[i++];
        if (c < 128) continue;
        int n;
        uint32_t minimum;
        if (c >= 0xc2 && c <= 0xdf) { n = 1; c &= 0x1f; minimum = 0x80; }
        else if (c >= 0xe0 && c <= 0xef) { n = 2; c &= 0x0f; minimum = 0x800; }
        else if (c >= 0xf0 && c <= 0xf4) { n = 3; c &= 7; minimum = 0x10000; }
        else return false;
        if (i + n > s.size()) return false;
        while (n--) {
            const uint8_t next = (uint8_t) s[i++];
            if ((next & 0xc0) != 0x80) return false;
            c = (c << 6) | (next & 0x3f);
        }
        if (c < minimum || c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff)) return false;
    }
    return true;
}

void validate_source(const std::string& source) {
    if (source.empty() || source.size() > kMaxSourceBytes || source.find('\0') != std::string::npos ||
        !valid_utf8(source))
        throw std::runtime_error("grammar must be 1..8192 UTF-8 bytes without a raw NUL");
    // An admission scan only; XGrammar remains the sole parser and matcher.
    // Initially exclude attributes, lookahead, macros, regex and range expansion.
    static const std::regex attributes(R"((^|\n)[ \t]*[A-Za-z_][A-Za-z0-9_.-]*[ \t]*\[[^\n]*\][ \t]*::=)");
    if (std::regex_search(source, attributes)) throw std::runtime_error("grammar rule attributes are unsupported");
    bool quote = false, cls = false, comment = false, escape = false;
    int depth = 0, alternatives = 0, rules = 0;
    for (size_t i = 0; i < source.size(); ++i) {
        const char c = source[i];
        if (comment) { if (c == '\n') comment = false; continue; }
        if (escape) { escape = false; continue; }
        if (quote || cls) {
            if (c == '\\') escape = true;
            else if (quote && c == '"') quote = false;
            else if (cls && c == ']') cls = false;
            continue;
        }
        if (c == '#') comment = true;
        else if (c == '"') quote = true;
        else if (c == '[') cls = true;
        else if (c == '(' && ++depth > 32) throw std::runtime_error("grammar nesting exceeds 32 groups");
        else if (c == ')' && --depth < 0) throw std::runtime_error("unmatched grammar closing group");
        else if (c == '|' && ++alternatives > 256) throw std::runtime_error("grammar exceeds 256 alternatives");
        else if (c == ':' && source.compare(i, 3, "::=") == 0 && ++rules > 128)
            throw std::runtime_error("grammar exceeds 128 rules");
        else if (c == '{' || c == '}' || c == '/' || c == '@' || c == '<' || c == '>' || c == '!' || c == '$')
            throw std::runtime_error("unsupported grammar extension (ranges, regex, macros, lookahead or token literals)");
    }
    if (depth != 0 || quote || cls || escape) throw std::runtime_error("unclosed grammar group, literal or character class");
}

struct Compiled {
    std::shared_ptr<const Vocabulary> vocabulary;
    std::string source;
    std::string identity;
    xgrammar::CompiledGrammar grammar;
    size_t bytes;
    Compiled(std::shared_ptr<const Vocabulary> v, std::string s, xgrammar::CompiledGrammar g)
        : vocabulary(std::move(v)), source(std::move(s)),
          identity(std::string(kBackend) + ":" + vocabulary->identity + ":" + source_identity(source)),
          grammar(std::move(g)), bytes(grammar.MemorySizeBytes() + source.size()) {}
};

struct Matcher::Impl {
    std::shared_ptr<const Compiled> compiled;
    xgrammar::GrammarMatcher matcher;
    detail::WorkBudget budget;
    std::vector<int32_t> history, bitmask;
    size_t output_bytes = 0;
    bool dirty = true, failed = false;
    explicit Impl(std::shared_ptr<const Compiled> c, uint64_t limit)
        : compiled(std::move(c)), matcher(compiled->grammar, std::nullopt, false), budget{limit},
          bitmask((compiled->vocabulary->bytes.size() + 31) / 32) {}
    Impl(const Impl& from)
        : compiled(from.compiled), matcher(from.matcher.Fork()), budget(from.budget), history(from.history),
          bitmask(from.bitmask), output_bytes(from.output_bytes), dirty(from.dirty), failed(from.failed) {}
    void usable() const {
        if (failed) throw std::runtime_error("grammar matcher failed; discard this generation");
    }
};

Matcher::Matcher(std::shared_ptr<const Compiled> c, uint64_t limit) {
    if (!c) throw std::runtime_error("missing compiled grammar");
    detail::WorkBudget budget{limit};
    detail::WorkScope scope(budget, 1000ms);
    impl_ = std::make_unique<Impl>(std::move(c), limit);
    impl_->budget = budget;
    scope.finish();
}
Matcher::Matcher(std::unique_ptr<Impl> impl) : impl_(std::move(impl)) {}
Matcher::~Matcher() = default;
Matcher::Matcher(Matcher&&) noexcept = default;
Matcher& Matcher::operator=(Matcher&&) noexcept = default;

const std::vector<int32_t>& Matcher::mask() {
    auto& p = *impl_;
    p.usable();
    if (p.matcher.IsTerminated()) throw std::runtime_error("grammar matcher is terminal");
    if (!p.dirty) return p.bitmask;
    try {
        detail::WorkScope scope(p.budget, 1000ms);
        int64_t shape[2] = {1, (int64_t) p.bitmask.size()};
        DLTensor tensor{};
        tensor.data = p.bitmask.data(); tensor.device = {kDLCPU, 0};
        tensor.ndim = 2; tensor.dtype = {kDLInt, 32, 1}; tensor.shape = shape;
        p.matcher.FillNextTokenBitmask(&tensor);
        // Always exclude padding beyond the vocabulary, including from an all-true mask.
        const size_t n = p.compiled->vocabulary->bytes.size();
        if (n % 32) p.bitmask.back() = (int32_t) ((uint32_t) p.bitmask.back() & ((1u << (n % 32)) - 1));
        if (std::all_of(p.bitmask.begin(), p.bitmask.end(), [](int32_t word) { return word == 0; }))
            throw std::runtime_error("grammar has no tokenizer-realizable continuation");
        scope.finish();
        p.dirty = false;
        return p.bitmask;
    } catch (...) { p.failed = true; throw; }
}

bool Matcher::allows(int32_t token) {
    if (token < 0 || (size_t) token >= impl_->compiled->vocabulary->bytes.size()) return false;
    const auto& m = mask();
    return ((uint32_t) m[(size_t) token / 32] & (1u << (token % 32))) != 0;
}

bool Matcher::accept(int32_t token) {
    auto& p = *impl_;
    p.usable();
    if (!allows(token)) return false;
    try {
        const size_t bytes = p.compiled->vocabulary->bytes[(size_t) token].size();
        if (p.history.size() >= kMaxHistoryTokens || p.output_bytes + bytes > kMaxOutputBytes)
            throw std::runtime_error("grammar resource limit: generation history exceeds its bound");
        detail::WorkScope scope(p.budget, 1000ms);
        if (!p.matcher.AcceptToken(token)) throw std::runtime_error("native grammar rejected an allowed token");
        scope.finish();
        p.history.push_back(token); p.output_bytes += bytes; p.dirty = true;
        return true;
    } catch (...) { p.failed = true; throw; }
}

bool Matcher::complete() const { impl_->usable(); return impl_->matcher.IsCompleted(); }
bool Matcher::terminated() const { impl_->usable(); return impl_->matcher.IsTerminated(); }
bool Matcher::failed() const { return impl_->failed; }
const std::vector<int32_t>& Matcher::tokens() const { return impl_->history; }
const std::string& Matcher::identity() const { return impl_->compiled->identity; }
uint64_t Matcher::work_used() const { return impl_->budget.used; }

Matcher Matcher::fork() const {
    impl_->usable();
    detail::WorkScope scope(impl_->budget, 1000ms);
    auto copy = std::make_unique<Impl>(*impl_);
    scope.finish();
    return Matcher(std::move(copy));
}

Checkpoint Matcher::checkpoint() const {
    impl_->usable();
    return {impl_->compiled, impl_->history};
}

void Matcher::restore(const Checkpoint& checkpoint) {
    impl_->usable();
    if (checkpoint.compiled != impl_->compiled)
        throw std::runtime_error("grammar/tokenizer/backend identity mismatch in checkpoint");
    if (checkpoint.tokens.size() > kMaxHistoryTokens) throw std::runtime_error("grammar checkpoint is too large");
    Matcher fresh(impl_->compiled, impl_->budget.remaining);
    for (int32_t t : checkpoint.tokens)
        if (!fresh.accept(t)) throw std::runtime_error("invalid grammar checkpoint token");
    fresh.impl_->budget.used += impl_->budget.used;
    *this = std::move(fresh);
}

struct Compiler::Impl {
    std::shared_ptr<const Vocabulary> vocabulary;
    xgrammar::TokenizerInfo tokenizer;
    xgrammar::GrammarCompiler compiler;
    std::list<std::shared_ptr<const Compiled>> cache;
    size_t entries_limit, bytes_limit, bytes = 0;
    Impl(std::shared_ptr<const Vocabulary> v, size_t entries, size_t maximum)
        : vocabulary(std::move(v)), tokenizer(vocabulary->bytes, xgrammar::VocabType::RAW,
                                              (int) vocabulary->bytes.size(), vocabulary->stop_ids, false),
          compiler(tokenizer, 1, false), entries_limit(entries), bytes_limit(maximum) {}
};

Compiler::Compiler(std::shared_ptr<const Vocabulary> v, size_t entries, size_t bytes) {
    if (!v || entries > 64 || bytes > 256 * 1024 * 1024)
        throw std::runtime_error("invalid grammar compiler configuration");
    xgrammar::SetMaxRecursionDepth(128);
    impl_ = std::make_unique<Impl>(std::move(v), entries, bytes);
}
Compiler::~Compiler() = default;
size_t Compiler::cache_entries() const { return impl_->cache.size(); }
size_t Compiler::cache_bytes() const { return impl_->bytes; }

std::shared_ptr<const Compiled> Compiler::compile(const std::string& source, uint64_t limit) {
    validate_source(source);
    auto& p = *impl_;
    for (auto i = p.cache.begin(); i != p.cache.end(); ++i)
        if ((*i)->source == source) {
            const auto compiled = *i;
            p.cache.splice(p.cache.begin(), p.cache, i);
            return compiled;
        }
    detail::WorkBudget budget{limit};
    detail::WorkScope scope(budget, 2500ms);
    auto result = std::make_shared<Compiled>(p.vocabulary, source, p.compiler.CompileGrammar(source, "root"));
    if (result->bytes > 16 * 1024 * 1024)
        throw std::runtime_error("grammar resource limit: compiled grammar exceeds 16 MiB");
    scope.finish();
    Matcher initial(result);
    initial.mask(); // No unproductive/unrealizable grammar enters the cache or falls back to plain decoding.
    if (p.entries_limit && result->bytes <= p.bytes_limit) {
        while (p.cache.size() >= p.entries_limit || p.bytes + result->bytes > p.bytes_limit) {
            p.bytes -= p.cache.back()->bytes; p.cache.pop_back();
        }
        p.cache.push_front(result); p.bytes += result->bytes;
    }
    return result;
}

} // namespace strata::grammar
