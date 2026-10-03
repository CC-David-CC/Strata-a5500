// Native raw-GBNF constraints. Immutable compilation is shared; progress is private.
#pragma once

#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>
#include <vector>

namespace strata::grammar {

inline constexpr const char* kBackend = "xgrammar-0.2.8-strata-budget1";
inline constexpr size_t kMaxSourceBytes = 8192;
inline constexpr size_t kMaxHistoryTokens = 8192;
inline constexpr size_t kMaxOutputBytes = 65536;

struct Vocabulary {
    // Actual emitted bytes. Special/control/unused IDs have empty strings and
    // cannot be selected as text. Stop IDs are separate control transitions.
    std::vector<std::string> bytes;
    std::vector<int32_t> stop_ids;
    std::string identity; // stable diagnostic fingerprint, not an authentication token
    static std::shared_ptr<const Vocabulary> from_pack(const std::filesystem::path& path,
                                                      std::vector<int32_t> stop_ids);
    static std::shared_ptr<const Vocabulary> from_bytes(std::vector<std::string> bytes,
                                                       std::vector<int32_t> stop_ids);
};

struct Compiled;
struct Checkpoint {
    std::shared_ptr<const Compiled> compiled;
    std::vector<int32_t> tokens;
};

class Matcher {
public:
    explicit Matcher(std::shared_ptr<const Compiled> compiled, uint64_t work_limit = 2000000);
    ~Matcher();
    Matcher(Matcher&&) noexcept;
    Matcher& operator=(Matcher&&) noexcept;
    Matcher(const Matcher&) = delete;
    Matcher& operator=(const Matcher&) = delete;
    const std::vector<int32_t>& mask();
    bool allows(int32_t token);
    bool accept(int32_t token); // illegal token: false with no state change
    bool complete() const;     // accepting prefix, possibly with legal continuations
    bool terminated() const;   // an allowed end control was committed
    bool failed() const;
    Matcher fork() const;
    Checkpoint checkpoint() const;
    void restore(const Checkpoint& checkpoint);
    const std::vector<int32_t>& tokens() const;
    const std::string& identity() const;
    uint64_t work_used() const;
private:
    struct Impl;
    explicit Matcher(std::unique_ptr<Impl> impl);
    std::unique_ptr<Impl> impl_;
};

class Compiler {
public:
    explicit Compiler(std::shared_ptr<const Vocabulary> vocabulary, size_t entries = 8,
                      size_t cache_bytes = 64 * 1024 * 1024);
    ~Compiler();
    Compiler(const Compiler&) = delete;
    Compiler& operator=(const Compiler&) = delete;
    std::shared_ptr<const Compiled> compile(const std::string& source,
                                          uint64_t work_limit = 5000000);
    size_t cache_entries() const;
    size_t cache_bytes() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

void validate_source(const std::string& source);
bool valid_utf8(const std::string& text);

} // namespace strata::grammar
