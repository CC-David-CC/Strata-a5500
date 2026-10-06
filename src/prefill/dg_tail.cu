// Host adapter for DeepSeek DeepGEMM's SM120 BF16 kernel, nv_dev b64107f2.
// Kernel implementation remains in the external DeepGEMM headers:
// https://github.com/deepseek-ai/DeepGEMM/tree/nv_dev
// No Torch, Python, model pruning or cached BF16 expert copies at runtime.
#include "strata/prefill/dg_tail.hpp"
#include <cuda.h>
#include <cuda_runtime.h>
#include <cuda_bf16.h>
#include <cuda_fp16.h>
#include <deep_gemm/impls/sm120_bf16_gemm.cuh>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>

namespace strata::prefill::dg_tail {
namespace {
constexpr int K = 640, N = 2560, Groups = 4, Capacity = 6144;
constexpr int Smem = 32 * 64 * 2 + 7 * (32 * 64 * 2 + 64 * 64 * 2) + 14 * 8;
using BF = cutlass::bfloat16_t;
using Epi = deep_gemm::epilogue::transform::EpilogueIdentity;
static auto kernel() {
    return &deep_gemm::sm120_bf16_gemm_impl<0, N, K, Groups, 32, 64, 64,
        128, 128, 128, 7, 128, 256, 188, deep_gemm::GemmType::MGroupedContiguous,
        false, BF, Epi, true, 4, false, 128>;
}
bool flag(const char* name) { const char* s = std::getenv(name); return s && std::atoi(s) != 0; }
void checked(cudaError_t e) { if (e != cudaSuccess) throw std::runtime_error(cudaGetErrorString(e)); }
void checked(CUresult e) {
    if (e != CUDA_SUCCESS) { const char* s = nullptr; cuGetErrorString(e, &s); throw std::runtime_error(s ? s : "CUDA driver error"); }
}
__global__ void decode_q8(const uint8_t* raw, BF* dst, int values) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= values) return;
    const uint8_t* q = raw + (i / 32) * 34;
    const float scale = __half2float(*reinterpret_cast<const __half*>(q));
    dst[i] = BF(__fmul_rn(scale, float(reinterpret_cast<const int8_t*>(q + 2)[i % 32])));
}
// Bounds are passed by value: no host-buffer lifetime or asynchronous upload.
__global__ void pack_h(const float* src, BF* dst, int32_t* labels, int32_t* map,
                       int c0, int c1, int c2, int c3, int packed) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= packed * K) return;
    const int row = i / K, col = i % K;
    const int counts[4] = {c0, c1, c2, c3};
    int p0 = 0, r0 = 0, original = -1, group = -1;
    #pragma unroll
    for (int e = 0; e < Groups; ++e) {
        const int p1 = p0 + ((counts[e] + 31) / 32) * 32;
        if (row >= p0 && row < p1 && row - p0 < counts[e]) { original = r0 + row - p0; group = e; }
        p0 = p1; r0 += counts[e];
    }
    dst[i] = BF(original >= 0 ? src[original * K + col] : 0.0f);
    if (col == 0) { map[row] = original; labels[row] = group; }
}
__global__ void unpack_d(const BF* src, float* dst, const int32_t* map, int packed) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= packed * N) return;
    const int original = map[i / N];
    if (original >= 0) dst[original * N + i % N] = float(src[i]);
}
CUtensorMap tma(void* data, int inner, int outer, int box_outer) {
    CUtensorMap result{};
    const cuuint64_t dims[] = {cuuint64_t(inner), cuuint64_t(outer)};
    const cuuint64_t stride[] = {cuuint64_t(inner * sizeof(BF))};
    const cuuint32_t box[] = {64, cuuint32_t(box_outer)}, step[] = {1, 1};
    checked(cuTensorMapEncodeTiled(&result, CU_TENSOR_MAP_DATA_TYPE_BFLOAT16, 2,
        data, dims, stride, box, step, CU_TENSOR_MAP_INTERLEAVE_NONE,
        CU_TENSOR_MAP_SWIZZLE_128B, CU_TENSOR_MAP_L2_PROMOTION_L2_256B, CU_TENSOR_MAP_FLOAT_OOB_FILL_NONE));
    return result;
}
}

struct Context::Impl {
    int device = 0;
    BF *weights = nullptr, *activations = nullptr, *output = nullptr;
    int32_t *labels = nullptr, *map = nullptr;
    uint64_t calls = 0;
    Impl() {
        checked(cudaGetDevice(&device));
        checked(cudaFuncSetAttribute(kernel(), cudaFuncAttributeMaxDynamicSharedMemorySize, Smem));
        try {
            checked(cudaMalloc(&weights, size_t(Groups) * N * K * sizeof(BF)));
            checked(cudaMalloc(&activations, size_t(Capacity) * K * sizeof(BF)));
            checked(cudaMalloc(&output, size_t(Capacity) * N * sizeof(BF)));
            checked(cudaMalloc(&labels, Capacity * sizeof(int32_t)));
            checked(cudaMalloc(&map, Capacity * sizeof(int32_t)));
        } catch (...) { release(); throw; }
    }
    void release() {
        int previous = 0; cudaGetDevice(&previous); cudaSetDevice(device);
        cudaFree(weights); cudaFree(activations); cudaFree(output); cudaFree(labels); cudaFree(map);
        weights = activations = output = nullptr; labels = map = nullptr;
        cudaSetDevice(previous);
    }
    ~Impl() { std::fprintf(stderr, "strata dg tail: %llu native down replacements\n", (unsigned long long) calls); release(); }
};
Context::Context() {
    enabled_ = flag("STRATA_DEEPGEMM_TAIL");
    if (!enabled_ && !flag("STRATA_DEEPGEMM_TAIL_RESERVE")) return;
    int dev = 0; cudaDeviceProp props{};
    checked(cudaGetDevice(&dev)); checked(cudaGetDeviceProperties(&props, dev));
    if (props.major != 12 || props.minor != 0 || props.multiProcessorCount != 188)
        throw std::runtime_error("DeepGEMM tail pilot requires SM120 with 188 SMs");
    impl_ = std::make_unique<Impl>();
    std::fprintf(stderr, "strata dg tail: SM120 BF16 down pilot %s; 50 MiB scratch reserved\n", enabled_ ? "on" : "control");
}
Context::~Context() = default;
bool Context::ready() const { return impl_ != nullptr; }
bool Context::selected(int type, int experts, int64_t max_rows, int64_t total_rows) const {
    return enabled_ && ready() && type == 8 && experts == Groups && max_rows >= 512 && max_rows <= 1536 &&
        total_rows > 0 && Groups * max_rows >= 3 * total_rows;
}
bool Context::run(const void* raw, const float* h, const int32_t counts[4], float* dst, void* stream) {
    if (!ready() || !raw || !h || !dst || !counts) return false;
    int packed = 0;
    for (int e = 0; e < Groups; ++e) { if (counts[e] <= 0) return false; packed += ((counts[e] + 31) / 32) * 32; }
    if (packed > Capacity) return false;
    auto s = static_cast<cudaStream_t>(stream);
    Impl& c = *impl_;
    try {
        decode_q8<<<(Groups * N * K + 255) / 256, 256, 0, s>>>(static_cast<const uint8_t*>(raw), c.weights, Groups * N * K);
        pack_h<<<(packed * K + 255) / 256, 256, 0, s>>>(h, c.activations, c.labels, c.map, counts[0], counts[1], counts[2], counts[3], packed);
        checked(cudaPeekAtLastError());
        CUtensorMap a = tma(c.activations, K, packed, 32), b = tma(c.weights, K, Groups * N, 64), d = tma(c.output, N, packed, 32);
        BF* gd = c.output; const BF* gc = nullptr; BF *ga = nullptr, *gb = nullptr;
        cute::TmaDescriptor* buffer = nullptr; int* layout = c.labels;
        uint32_t m = packed, n = N, k = K, ld = N, zero = 0; Epi epilogue{};
        void* args[] = {&gd, &gc, &ga, &gb, &layout, &buffer, &m, &n, &k, &epilogue, &ld, &zero, &zero, &a, &b, &d};
        checked(cudaLaunchKernel(reinterpret_cast<const void*>(kernel()), dim3(188), dim3(384), args, Smem, s));
        unpack_d<<<(packed * N + 255) / 256, 256, 0, s>>>(c.output, dst, c.map, packed);
        checked(cudaPeekAtLastError());
        ++c.calls;
        return true;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "strata dg tail: %s\n", error.what());
        return false;
    }
}
}
