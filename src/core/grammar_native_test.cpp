#include "strata/core/grammar.hpp"
#include "strata/core/grammar_budget.hpp"
#include <picojson.h>

#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <unordered_map>

using namespace strata::grammar;
#define REQUIRE(x) do { if (!(x)) throw std::runtime_error(std::string("failed: ") + #x); } while (false)

static std::string read(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot read native grammar fixture: " + path.string());
    return {std::istreambuf_iterator<char>(in), {}};
}

template<class Fn> void fails(Fn fn, const std::string& message = "") {
    try { fn(); }
    catch (const std::exception& error) {
        REQUIRE(std::string(error.what()).find(message) != std::string::npos);
        return;
    }
    throw std::runtime_error("expected a grammar failure: " + message);
}

static void corpus(const std::filesystem::path& cases, const std::shared_ptr<const Vocabulary>& vocab) {
    picojson::value spec;
    REQUIRE(picojson::parse(spec, read(cases)).empty());
    Compiler compiler(vocab);
    std::unordered_map<std::string, int32_t> byte_id;
    for (size_t id = 0; id < vocab->bytes.size(); ++id)
        if (vocab->bytes[id].size() == 1) byte_id[vocab->bytes[id]] = (int32_t) id;
    REQUIRE(byte_id.size() == 256);
    size_t checks = 0;
    for (const auto& value : spec.get<picojson::array>()) {
        const auto& item = value.get<picojson::object>();
        const std::string filename = item.at("file").get<std::string>();
        auto compiled = compiler.compile(read(cases.parent_path() / filename));
        for (const std::string key : {"accept", "reject"}) {
            for (const auto& example : item.at(key).get<picojson::array>()) {
                Matcher matcher(compiled);
                bool accepted = true;
                for (char c : example.get<std::string>()) {
                    if (!matcher.accept(byte_id.at(std::string(1, c)))) { accepted = false; break; }
                }
                accepted = accepted && matcher.complete();
                REQUIRE(accepted == (key == "accept"));
                if (accepted) {
                    for (int32_t stop : vocab->stop_ids) {
                        auto ended = matcher.fork();
                        REQUIRE(ended.allows(stop) && ended.accept(stop) && ended.terminated());
                    }
                    REQUIRE(matcher.accept(vocab->stop_ids[0]));
                    REQUIRE(matcher.terminated());
                    fails([&] { matcher.mask(); }, "terminal");
                }
                ++checks;
            }
        }
        Matcher initial(compiled);
        for (size_t id = 0; id < vocab->bytes.size(); ++id)
            if (vocab->bytes[id].empty() &&
                std::find(vocab->stop_ids.begin(), vocab->stop_ids.end(), (int32_t) id) == vocab->stop_ids.end())
                REQUIRE(!initial.allows((int32_t) id));
        std::cout << "corpus " << filename << " passed\n";
    }
    std::cout << "corpus cases=" << checks << " vocabulary=" << vocab->bytes.size()
              << " identity=" << vocab->identity << "\n";
}

static void unit(const std::shared_ptr<const Vocabulary>& vocab) {
    Compiler c(vocab, 2, 64 * 1024 * 1024);
    const auto overlap = c.compile("root ::= \"a\" | \"ab\"");
    Matcher parent(overlap);
    REQUIRE(!parent.allows(256) && !parent.allows(257)); // stop and special
    REQUIRE(!parent.accept('x') && parent.tokens().empty());
    REQUIRE(parent.accept('a') && parent.complete());
    REQUIRE(parent.allows('b') && parent.allows(256));
    const auto snapshot = parent.checkpoint();
    auto left = parent.fork(), right = parent.fork();
    REQUIRE(left.accept('b') && left.accept(256));
    REQUIRE(right.accept(256));
    REQUIRE(parent.tokens().size() == 1 && !parent.terminated());
    left.restore(snapshot);
    REQUIRE(left.tokens() == parent.tokens() && !left.terminated());
    Matcher wrong(c.compile("root ::= \"z\""));
    REQUIRE(parent.identity() != wrong.identity());
    fails([&] { wrong.restore(snapshot); }, "identity mismatch");
    auto different_bytes = vocab->bytes;
    different_bytes['a'] = "q";
    Compiler other(Vocabulary::from_bytes(std::move(different_bytes), {256}));
    Matcher mismatch(other.compile("root ::= \"a\" | \"ab\""));
    fails([&] { mismatch.restore(snapshot); }, "identity mismatch");
    REQUIRE(c.compile("root ::= \"a\" | \"ab\"") == overlap);
    c.compile("root ::= \"b\"");
    c.compile("root ::= \"c\"");
    REQUIRE(c.cache_entries() == 2 && c.cache_bytes() <= 64 * 1024 * 1024);
    REQUIRE(parent.accept('b')); // eviction cannot mutate an active sequence
    REQUIRE(parent.complete());
    Matcher multi(c.compile("root ::= \"a\" \"b\""));
    REQUIRE(multi.accept(259) && multi.complete());
    Matcher utf(c.compile("root ::= \"caf\xc3\xa9\""));
    REQUIRE(utf.accept('c') && utf.accept('a') && utf.accept('f'));
    REQUIRE(utf.accept(0xc3) && !utf.complete());
    REQUIRE(utf.allows(0xa9) && !utf.allows('x'));
    REQUIRE(utf.accept(0xa9) && utf.complete());
    Matcher loop(c.compile("root ::= \"(\" root \")\" root | \"\""));
    for (int i = 0; i < 32; ++i) REQUIRE(loop.accept('('));
    for (int i = 0; i < 32; ++i) REQUIRE(loop.accept(')'));
    REQUIRE(loop.complete());
    Matcher epsilon(c.compile("root ::= \"\""));
    REQUIRE(epsilon.complete() && epsilon.allows(256) && !epsilon.allows('a'));
    Matcher ambiguous(c.compile("root ::= root root | \"a\""));
    for (int i = 0; i < 24; ++i) REQUIRE(ambiguous.accept('a') && ambiguous.complete());

    fails([&] { c.compile("root ::= root"); });
    fails([&] { c.compile("root ::= missing"); });
    fails([&] { c.compile("root ::= \"unterminated"); });
    fails([&] { c.compile("root ::= )[a]("); }, "closing group");
    fails([&] { c.compile("root ::= \"a\"{100000000}"); }, "unsupported");
    fails([&] { c.compile("root[temperature=0.1] ::= \"a\""); }, "attributes");
    fails([&] { c.compile(std::string(kMaxSourceBytes + 1, 'a')); }, "8192");
    fails([&] { c.compile(std::string("root ::= \"a\"\0", 13)); }, "NUL");
    REQUIRE(!valid_utf8("\xc0\x80") && !valid_utf8("\xed\xa0\x80") && !valid_utf8("\xf4\x90\x80\x80"));
    REQUIRE(valid_utf8("\xe7\x8c\xab"));
    Compiler no_cache(vocab, 0, 0);
    fails([&] { no_cache.compile("root ::= \"bounded\"", 0); }, "work budget");
    fails([&] { no_cache.compile("root ::= \"" + std::string(512, 'x') + "\"", 100); }, "work budget");
    const auto bounded = no_cache.compile("root ::= [ab]*");
    Matcher limited(bounded, 48);
    fails([&] { for (int i = 0; i < 100; ++i) REQUIRE(limited.accept('a')); }, "work budget");
    REQUIRE(limited.failed());
    fails([&] { limited.mask(); }, "discard");
    // A failed operation does not poison the compiler or a new sequence.
    Matcher fresh(no_cache.compile("root ::= \"ok\""));
    REQUIRE(fresh.accept('o') && fresh.accept('k') && fresh.complete());
    Compiler impossible(Vocabulary::from_bytes({"a", ""}, {1}));
    fails([&] { impossible.compile("root ::= \"z\""); }, "no tokenizer-realizable continuation");
    detail::WorkBudget deadline{10};
    detail::WorkScope scope(deadline, std::chrono::milliseconds(100));
    deadline.deadline = std::chrono::steady_clock::now() - std::chrono::seconds(1);
    fails([&] { detail::work(); }, "deadline");
    std::cout << "native masks, UTF-8 fragments, recursion, accepting prefixes, stop/special IDs, forks, "
                 "checkpoints, cache isolation, syntax and resource failures passed\n";
}

static void dump_vocab(const Vocabulary& vocab, const std::filesystem::path& path) {
    std::ofstream out(path, std::ios::binary);
    auto u32 = [&](uint32_t v) { for (int i = 0; i < 4; ++i) out.put((char) (v >> (i * 8))); };
    out.write("SVOC1", 5); u32((uint32_t) vocab.bytes.size());
    for (const auto& token : vocab.bytes) { u32((uint32_t) token.size()); out.write(token.data(), token.size()); }
    if (!out) throw std::runtime_error("vocabulary audit write failed");
}

int main(int argc, char** argv) {
    try {
        if (argc != 2 && argc != 4) throw std::runtime_error("usage: grammar_native_test CASES [TOKENIZER_DIR VOCAB_AUDIT]");
        std::vector<std::string> bytes;
        for (int i = 0; i < 256; ++i) bytes.push_back(std::string(1, (char) i));
        bytes.insert(bytes.end(), {"", "", "true", "ab", "()"});
        auto vocab = Vocabulary::from_bytes(std::move(bytes), {256});
        corpus(argv[1], vocab);
        unit(vocab);
        if (argc == 4) {
            auto actual = Vocabulary::from_pack(argv[2], {248044, 248046});
            corpus(argv[1], actual);
            dump_vocab(*actual, argv[3]);
        }
        std::cout << "grammar native tests passed (" << kBackend << ")\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "grammar native test failed: " << error.what() << '\n';
        return 1;
    }
}
