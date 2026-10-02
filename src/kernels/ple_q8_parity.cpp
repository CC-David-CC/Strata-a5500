// Q8_0 PLE rows against ggml, including synthetic signed/scaled and file-boundary cases.
#define NOMINMAX
#include "strata/artifact/gguf_reader.hpp"
#include "strata/kernels/ngram.hpp"
#include "ggml.h"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <random>
#include <string>
#include <vector>

namespace k = strata::kernels;
namespace {

void append_le(std::vector<uint8_t>& bytes, uint64_t x, int n) {
    for (int i = 0; i < n; ++i) bytes.push_back((uint8_t) (x >> (8 * i)));
}

std::vector<uint8_t> fixture(uint32_t type = 8, uint64_t width = 160, uint64_t rows = 64) {
    std::vector<uint8_t> bytes;
    append_le(bytes, 0x46554747, 4); append_le(bytes, 3, 4);
    append_le(bytes, 1, 8); append_le(bytes, 0, 8);
    const std::string name = "per_layer_token_embd.weight";
    append_le(bytes, name.size(), 8); bytes.insert(bytes.end(), name.begin(), name.end());
    append_le(bytes, 2, 4); append_le(bytes, width, 8); append_le(bytes, rows, 8);
    append_le(bytes, type, 4); append_le(bytes, 0, 8);
    while (bytes.size() % 32) bytes.push_back(0);
    const uint16_t scales[] = {0x0000, 0x8000, 0x0001, 0x0400, 0x3555, 0x3c00, 0xbc00, 0x7bff};
    // Always 64 physical rows, so a malicious row count can be checked without allocating it.
    for (int r = 0; r < 64; ++r)
        for (int b = 0; b < 5; ++b) {
            append_le(bytes, scales[(r + b) % 8], 2);
            for (int j = 0; j < 32; ++j) bytes.push_back((uint8_t) ((r * 97 + b * 31 + j * 17) & 255));
        }
    return bytes;
}

bool compare(const std::string& path) {
    strata::GgufFile gguf(path);
    const auto* tensor = gguf.find("per_layer_token_embd.weight");
    if (!tensor || tensor->type != 8 || tensor->shape.size() != 2 || tensor->shape[0] != 160) return false;
    k::PleTable table;
    k::PleIoOptions options; options.mode = k::PleIo::Mmap;
    std::string err;
    if (!table.open(path, err, options)) { std::fprintf(stderr, "%s\n", err.c_str()); return false; }
    if (std::strcmp(table.format(), "Q8_0") || table.bytes_read() != 0) return false;
    const auto* traits = ggml_get_type_traits(GGML_TYPE_Q8_0);
    const uint8_t* bytes = gguf.tensor_data(*tensor);
    std::vector<uint32_t> probes = {0, 1, (uint32_t) (table.rows() - 1)};
    const uint64_t base = gguf.data_start() + tensor->offset;
    for (uint32_t r = 0; r < table.rows() && probes.size() < 35; ++r)
        if ((base + (uint64_t) r * 170) / 4096 != (base + (uint64_t) r * 170 + 169) / 4096)
            probes.push_back(r);
    std::mt19937 rng(71);
    for (int i = 0; i < 1024; ++i) probes.push_back((uint32_t) (rng() % table.rows()));
    for (uint32_t row : probes) {
        float got[160], want[160];
        table.read_row(row, got);
        traits->to_float(bytes + (size_t) row * 170, want, 160);
        if (std::memcmp(got, want, sizeof got)) {
            std::fprintf(stderr, "row %u differs from ggml\n", row); return false;
        }
    }
    uint32_t rows[32];
    for (int i = 0; i < 32; ++i) rows[i] = probes[i % probes.size()];
    float issued[16 * 160], gathered[32 * 160];
    if (!table.issue(rows) || !table.collect(issued, err)) return false;
    if (!table.gather_batch(rows, 2, gathered, err)) return false;
    if (std::memcmp(issued, gathered, sizeof issued)) return false;
    for (int h = 0; h < 32; ++h) {
        float want[160];
        traits->to_float(bytes + (size_t) rows[h] * 170, want, 160);
        if (std::memcmp(gathered + h * 160, want, sizeof want)) return false;
    }
    float outside[160], zeros[160] = {};
    table.read_row((uint32_t) table.rows(), outside);
    if (std::memcmp(outside, zeros, sizeof zeros)) return false;
    table.close();
    if (table.is_open() || table.bytes_read() != 0) return false;
    if (!table.open(path, err, options)) return false;
    k::PleIoOptions direct; direct.mode = k::PleIo::Direct;
    if (table.open(path, err, direct) || table.is_open() || err.find("Q8_0 PLE requires --ple-io mmap") == std::string::npos)
        return false;
    std::printf("Q8_0 PLE: %zu probes, row/batch/issue-collect bit-identical to ggml\n", probes.size());
    return true;
}

bool selftest() {
    const auto id = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto prefix = std::filesystem::temp_directory_path() / ("strata-ple-q8-" + std::to_string(id));
    bool ok = true;
    for (int arm = 0; arm < 5; ++arm) {
        auto bytes = fixture(arm == 3 ? 1 : 8, arm == 2 ? 159 : 160,
                             arm == 4 ? UINT64_MAX : 64);
        if (arm == 1) bytes.pop_back();
        const std::string path = prefix.string() + "-" + std::to_string(arm) + ".gguf";
        if (std::filesystem::exists(path)) return false;
        { std::ofstream f(path, std::ios::binary); f.write((const char*) bytes.data(), (std::streamsize) bytes.size()); }
        if (arm == 0) ok = compare(path) && ok;
        else {
            k::PleTable table; k::PleIoOptions opt; opt.mode = k::PleIo::Mmap; std::string err;
            if (table.open(path, err, opt) || table.is_open()) { std::fprintf(stderr, "accepted malformed arm %d\n", arm); ok = false; }
        }
        std::filesystem::remove(path);
    }
    return ok;
}
}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) { std::fprintf(stderr, "usage: ple_q8_parity --selftest | <Q8_0 PLE GGUF>\n"); return 2; }
    try {
        const bool ok = std::string(argv[1]) == "--selftest" ? selftest() : compare(argv[1]);
        std::printf("Q8_0 PLE %s\n", ok ? "PASS" : "FAIL");
        return ok ? 0 : 1;
    } catch (const std::exception& e) { std::fprintf(stderr, "%s\n", e.what()); return 1; }
}
