// Q8_0 row-tiling experiment: unchanged bytes and exact outputs against stock.
// --selftest: boundaries, odd output sizes, 1..8 columns, all candidate row tiles.
// --bench: model projection shapes; rotate >=512 MiB of weights to avoid timing
// just one small matrix resident in L2. Report graph GPU time, not application TPS.
#include "strata/kernels/native_mmvq.hpp"
#include <cuda_runtime.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace sk = strata::kernels;
namespace {
void ck(cudaError_t x) {
    if (x != cudaSuccess) throw std::runtime_error(cudaGetErrorString(x));
}
struct Device {
    void* p = nullptr;
    explicit Device(size_t n) { ck(cudaMalloc(&p, n)); }
    ~Device() { cudaFree(p); }
    Device(const Device&) = delete;
    Device& operator=(const Device&) = delete;
};
struct Shape { int in, out; };

void run(Shape shape, int columns, bool timing, cudaStream_t stream) {
    const size_t wb = sk::native_mmvq_weight_bytes(8, shape.in, shape.out);
    const size_t stride = (wb + 255) & ~size_t(255);
    const int copies = timing ? std::max(1, int((512ull*1024*1024 + stride-1)/stride)) : 1;
    const int steps = std::max(32, copies);
    std::mt19937 rng(20261002u + unsigned(shape.in + shape.out));
    std::vector<uint8_t> weights(wb);
    for (auto& v : weights) v = uint8_t(rng());
    for (size_t at = 0; at < wb; at += 34) {
        const uint16_t scale = uint16_t(((rng() & 1) << 15) | ((5 + rng()%5) << 10) | (rng() & 1023));
        std::memcpy(weights.data()+at, &scale, 2);
    }
    std::vector<float> x(size_t(columns)*shape.in);
    std::normal_distribution<float> dist(0, 1);
    for (auto& v : x) v = dist(rng);
    const size_t yb = size_t(columns)*shape.out*sizeof(float);
    Device w(stride*copies), dx(x.size()*sizeof(float)), xq(sk::native_q8_1_bytes(shape.in, columns)), y(yb);
    // Keep initialization on the same nonblocking stream as the kernels. A
    // pageable H2D copy on the default stream need not be complete when the
    // host call returns, and this stream does not implicitly wait for it.
    ck(cudaMemcpyAsync(w.p, weights.data(), wb, cudaMemcpyHostToDevice, stream));
    for (int i = 1; i < copies; ++i)
        ck(cudaMemcpyAsync((uint8_t*)w.p+stride*i, w.p, wb, cudaMemcpyDeviceToDevice, stream));
    ck(cudaMemcpyAsync(dx.p, x.data(), x.size()*sizeof(float), cudaMemcpyHostToDevice, stream));
    sk::native_quantize_q8_1((float*)dx.p, xq.p, shape.in, columns, stream);
    sk::native_mmvq_set_multi_exact(true);
    sk::native_q8_0_set_rows_per_block(0);
    sk::native_q8_0_mmvq(w.p, xq.p, (float*)y.p, shape.in, shape.out, columns, stream);
    ck(cudaStreamSynchronize(stream));
    std::vector<uint32_t> reference(yb/4), result(yb/4);
    ck(cudaMemcpy(reference.data(), y.p, yb, cudaMemcpyDeviceToHost));
    for (const int rows : {0, 1, 2, 4, 8}) {
        sk::native_q8_0_set_rows_per_block(rows);
        ck(cudaMemsetAsync(y.p, 0xff, yb, stream));
        sk::native_q8_0_mmvq(w.p, xq.p, (float*)y.p, shape.in, shape.out, columns, stream);
        ck(cudaStreamSynchronize(stream));
        ck(cudaMemcpy(result.data(), y.p, yb, cudaMemcpyDeviceToHost));
        size_t differences = 0, nonfinite = 0;
        for (size_t i = 0; i < result.size(); ++i) {
            float a, b;
            std::memcpy(&a, &reference[i], 4); std::memcpy(&b, &result[i], 4);
            differences += reference[i] != result[i];
            nonfinite += !std::isfinite(a) || !std::isfinite(b);
        }
        if (differences || nonfinite) {
            std::printf("FAIL in=%d out=%d T=%d rows=%d differences=%zu nonfinite=%zu\n",
                        shape.in, shape.out, columns, rows, differences, nonfinite);
            size_t shown = 0;
            for (size_t i = 0; i < result.size() && shown < 8; ++i) {
                if (reference[i] == result[i]) continue;
                float a, b;
                std::memcpy(&a, &reference[i], 4); std::memcpy(&b, &result[i], 4);
                std::printf("  index=%zu reference=%.9g (%08x) candidate=%.9g (%08x)\n",
                            i, a, reference[i], b, result[i]);
                ++shown;
            }
            throw std::runtime_error("row tile changed output");
        }
        if (!timing) continue;
        cudaGraph_t graph;
        cudaGraphExec_t exec;
        ck(cudaStreamBeginCapture(stream, cudaStreamCaptureModeThreadLocal));
        for (int i = 0; i < steps; ++i)
            sk::native_q8_0_mmvq((uint8_t*)w.p+stride*(i%copies), xq.p, (float*)y.p,
                                shape.in, shape.out, columns, stream);
        ck(cudaStreamEndCapture(stream, &graph));
        ck(cudaGraphInstantiate(&exec, graph, nullptr, nullptr, 0));
        ck(cudaGraphLaunch(exec, stream));
        ck(cudaStreamSynchronize(stream));
        cudaEvent_t start, end;
        ck(cudaEventCreate(&start)); ck(cudaEventCreate(&end));
        std::vector<float> times;
        for (int trial = 0; trial < 7; ++trial) {
            ck(cudaEventRecord(start, stream)); ck(cudaGraphLaunch(exec, stream));
            ck(cudaEventRecord(end, stream)); ck(cudaEventSynchronize(end));
            float ms;
            ck(cudaEventElapsedTime(&ms, start, end));
            times.push_back(ms*1000/steps);
        }
        std::sort(times.begin(), times.end());
        std::printf("BENCH {\"in\":%d,\"out\":%d,\"columns\":%d,\"rows\":%d,"
                    "\"weight_bytes\":%zu,\"working_set_bytes\":%zu,\"replays\":7,"
                    "\"median_us\":%.6f,\"min_us\":%.6f,\"max_us\":%.6f,"
                    "\"logical_weight_GBps\":%.3f,\"bit_differences\":0}\n",
                    shape.in, shape.out, columns, rows, wb, stride*copies,
                    times[3], times.front(), times.back(), double(wb)/times[3]/1000.0);
        std::fflush(stdout);
        cudaEventDestroy(start); cudaEventDestroy(end);
        cudaGraphExecDestroy(exec); cudaGraphDestroy(graph);
    }
    if (!timing) std::printf("PASS in=%d out=%d T=%d: tiles 0/1/2/4/8 match stock bit-for-bit\n",
                             shape.in, shape.out, columns);
}
}

int main(int argc, char** argv) {
    const bool bench = argc == 2 && std::string(argv[1]) == "--bench";
    if (argc != 2 || (!bench && std::string(argv[1]) != "--selftest")) {
        std::fprintf(stderr, "usage: q8_row_tile_bench --selftest|--bench\n");
        return 2;
    }
    try {
        cudaStream_t stream;
        ck(cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking));
        if (bench) {
            for (Shape s : {Shape{2560,10240}, {2560,6144}, {6144,2560}, {2560,12288},
                            {10240,320}, {2560,640}, {640,2560}, {2560,248320}})
                for (int t : {1,2,4}) run(s, t, true, stream);
        } else {
            for (Shape s : {Shape{32,1}, {32,17}, {640,513}, {2560,641}, {2560,10241}, {6144,2561}})
                for (int t = 1; t <= 8; ++t) run(s, t, false, stream);
            bool rejected = false;
            try { sk::native_q8_0_set_rows_per_block(3); }
            catch (const std::invalid_argument&) { rejected = true; }
            if (!rejected) throw std::runtime_error("invalid row policy accepted");
        }
        sk::native_q8_0_set_rows_per_block(0);
        ck(cudaStreamDestroy(stream));
        std::printf("Q8_ROW_TILE_%s_PASS\n", bench ? "BENCH" : "SELFTEST");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "FAILED: %s\n", e.what());
        return 1;
    }
}
