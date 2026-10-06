// Stage harness for the exact 0.1.40 MMQ implementation; no engine modification.
#include "strata/prefill/moe_mmq.hpp"
#include <cuda_bf16.h>
#include <cuda_fp16.h>
#include <cuda_runtime.h>
#include <cstdint>
#include <cstring>
namespace mmq = strata::prefill::mmq;

extern "C" void* context_create() { return new mmq::Context(); }
extern "C" void context_destroy(void* p) { delete static_cast<mmq::Context*>(p); }
extern "C" size_t activation_bytes(int rows, int cols) { return mmq::q8_bytes(rows, cols); }
extern "C" void quantize(const float* x, void* xq, int cols, int rows, void* stream) {
    mmq::quantize(x, nullptr, xq, 8, cols, cols, rows, stream);
}
extern "C" void product(void* context, const void* w, const void* xq,
                         const int32_t* bounds, const int32_t* ids,
                         float* dst, int groups, int rows, int max_rows,
                         int n, int k, void* stream) {
    mmq::Product p;
    p.w=w; p.type=8; p.w_rows=n; p.w_cols=k;
    p.expert_bytes=mmq::matrix_bytes(8,n,k); p.n=groups;
    p.xq=xq; p.bounds=bounds; p.ids=ids;
    p.total_rows=rows; p.max_rows=max_rows; p.dst=dst; p.ld_dst=n;
    static_cast<mmq::Context*>(context)->run(p, stream);
}
extern "C" void swiglu(const float* gu, float* h, int rows, void* stream) {
    mmq::swiglu(gu,h,rows,640,false,stream);
}

// Convert original Q8_0 bytes at each stage, charging the conversion for streamed
// weights. Scalar-format agreement is checked against the independent CPU oracle.
__global__ void q8_bf16(const uint8_t* raw, __nv_bfloat16* dst, int64_t count) {
    int64_t i=static_cast<int64_t>(blockIdx.x)*blockDim.x+threadIdx.x;
    if(i>=count) return;
    const uint8_t* block=raw+(i/32)*34;
    uint16_t bits=static_cast<uint16_t>(block[0]) | (static_cast<uint16_t>(block[1])<<8);
    __half scale; memcpy(&scale,&bits,sizeof(bits));
    float value=__half2float(scale)*static_cast<float>(reinterpret_cast<const int8_t*>(block+2)[i%32]);
    dst[i]=__float2bfloat16_rn(value);
}
extern "C" void dequantize_bf16(const void* raw, void* dst, int64_t count, void* stream) {
    q8_bf16<<<(count+255)/256,256,0,static_cast<cudaStream_t>(stream)>>>(
        static_cast<const uint8_t*>(raw),static_cast<__nv_bfloat16*>(dst),count);
}

__global__ void pack_bf16(const float* src, __nv_bfloat16* dst, const int32_t* bounds,
                          int rows_cap, int cols, int64_t count) {
    int64_t i=static_cast<int64_t>(blockIdx.x)*blockDim.x+threadIdx.x;
    if(i>=count) return;
    int e=i/(static_cast<int64_t>(rows_cap)*cols), r=(i/cols)%rows_cap, k=i%cols;
    dst[i]=r<bounds[e+1]-bounds[e] ? __float2bfloat16_rn(src[(static_cast<int64_t>(bounds[e])+r)*cols+k])
                                 : __float2bfloat16_rn(0.0f);
}
__global__ void swiglu_bf16(const __nv_bfloat16* gu, __nv_bfloat16* h, const int32_t* counts,
                            int rows_cap, int64_t count) {
    int64_t i=static_cast<int64_t>(blockIdx.x)*blockDim.x+threadIdx.x;
    if(i>=count) return;
    int e=i/(static_cast<int64_t>(rows_cap)*640), r=(i/640)%rows_cap, k=i%640;
    if(r>=counts[e]) { h[i]=__float2bfloat16_rn(0.0f); return; }
    int64_t offset=(static_cast<int64_t>(e)*rows_cap+r)*1280+k;
    float g=__bfloat162float(gu[offset]), u=__bfloat162float(gu[offset+640]);
    h[i]=__float2bfloat16_rn((g/(1.0f+__expf(-g)))*u);
}
__global__ void unpack_f32(const __nv_bfloat16* src, float* dst, const int32_t* bounds,
                           int rows_cap, int cols, int64_t count) {
    int64_t i=static_cast<int64_t>(blockIdx.x)*blockDim.x+threadIdx.x;
    if(i>=count) return;
    int e=i/(static_cast<int64_t>(rows_cap)*cols), r=(i/cols)%rows_cap, k=i%cols;
    if(r<bounds[e+1]-bounds[e])
        dst[(static_cast<int64_t>(bounds[e])+r)*cols+k]=__bfloat162float(src[i]);
}
extern "C" void pack(const float* src, void* dst, const int32_t* bounds,
                      int groups, int rows_cap, int cols, void* stream) {
    int64_t n=static_cast<int64_t>(groups)*rows_cap*cols;
    pack_bf16<<<(n+255)/256,256,0,static_cast<cudaStream_t>(stream)>>>(
        src,static_cast<__nv_bfloat16*>(dst),bounds,rows_cap,cols,n);
}
extern "C" void activation(const void* gu, void* h, const int32_t* counts,
                            int groups, int rows_cap, void* stream) {
    int64_t n=static_cast<int64_t>(groups)*rows_cap*640;
    swiglu_bf16<<<(n+255)/256,256,0,static_cast<cudaStream_t>(stream)>>>(
        static_cast<const __nv_bfloat16*>(gu),static_cast<__nv_bfloat16*>(h),counts,rows_cap,n);
}
extern "C" void unpack(const void* src, float* dst, const int32_t* bounds,
                        int groups, int rows_cap, int cols, void* stream) {
    int64_t n=static_cast<int64_t>(groups)*rows_cap*cols;
    unpack_f32<<<(n+255)/256,256,0,static_cast<cudaStream_t>(stream)>>>(
        static_cast<const __nv_bfloat16*>(src),dst,bounds,rows_cap,cols,n);
}
