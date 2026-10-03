// Existing stdin command stream plus one bounded, inert grammar payload frame.
#pragma once
#include <charconv>
#include <cstddef>
#include <functional>
#include <optional>
#include <stdexcept>
#include <string>

namespace strata::program {
struct ServeRequest {
    std::string line, grammar, error;
    bool fatal = false;
};

// GENG1 <UTF-8 byte count>\n<exact grammar bytes>\nGEN <arguments>\n
// A malformed/truncated frame terminates this pipe; its body is never reparsed
// as commands. The caller owns the existing queue and STOP/cancellation flag.
class ServeInput {
public:
    explicit ServeInput(std::function<std::ptrdiff_t(char*, size_t)> read) : read_(std::move(read)) {}
    std::optional<ServeRequest> next() {
        if (finished_) return std::nullopt;
        ServeRequest request;
        try {
            bool terminated = false;
            if (!line(request.line, terminated)) { finished_ = true; return std::nullopt; }
            if (request.line.rfind("GENG", 0) != 0) return request;
            if (!terminated || request.line.rfind("GENG1 ", 0) != 0)
                throw std::runtime_error("unsupported or truncated grammar frame header");
            size_t count = 0;
            const char* start = request.line.data() + 6;
            const char* end = request.line.data() + request.line.size();
            const auto number = std::from_chars(start, end, count);
            if (number.ec != std::errc{} || number.ptr != end || count < 1 || count > 8192)
                throw std::runtime_error("grammar frame length must be 1..8192 bytes");
            request.grammar = bytes(count);
            if (bytes(1) != "\n") throw std::runtime_error("grammar frame delimiter is missing");
            if (!line(request.line, terminated) || !terminated || request.line.rfind("GEN ", 0) != 0 ||
                request.line.find('\0') != std::string::npos)
                throw std::runtime_error("grammar frame needs one complete GEN command");
            return request;
        } catch (const std::exception& error) {
            finished_ = request.fatal = true;
            request.error = error.what();
            return request;
        }
    }
private:
    std::function<std::ptrdiff_t(char*, size_t)> read_;
    std::string buffer_;
    bool finished_ = false;
    bool more() {
        char chunk[4096];
        const auto n = read_(chunk, sizeof chunk);
        if (n < 0) throw std::runtime_error("native input read failed");
        if (n == 0) return false;
        buffer_.append(chunk, (size_t) n);
        return true;
    }
    bool line(std::string& out, bool& terminated) {
        for (;;) {
            const size_t nl = buffer_.find('\n');
            if (nl != std::string::npos) {
                if (nl > 4 * 1024 * 1024) throw std::runtime_error("native input line exceeds 4 MiB");
                out.assign(buffer_, 0, nl); buffer_.erase(0, nl + 1);
                if (!out.empty() && out.back() == '\r') out.pop_back();
                terminated = true;
                return true;
            }
            if (buffer_.size() > 4 * 1024 * 1024) throw std::runtime_error("native input line exceeds 4 MiB");
            if (!more()) { out.swap(buffer_); terminated = false; return !out.empty(); }
        }
    }
    std::string bytes(size_t count) {
        while (buffer_.size() < count)
            if (!more()) throw std::runtime_error("truncated grammar frame payload");
        std::string out = buffer_.substr(0, count);
        buffer_.erase(0, count);
        return out;
    }
};

inline std::string protocol_error(const std::string& message) {
    std::string out = message.substr(0, 512);
    for (char& ch : out) if ((unsigned char) ch < 32 || ch == 127) ch = ' ';
    return out;
}
} // namespace strata::program
