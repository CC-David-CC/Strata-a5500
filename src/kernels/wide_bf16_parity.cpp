// Each wide BF16 column must use the single-column arithmetic, including tails.
#include "strata/kernels/bf16_gemv.hpp"
#include "strata/spec/limits.hpp"
#include <cuda_runtime.h>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <stdexcept>
#include <vector>

static void ck(cudaError_t e) {
    if (e != cudaSuccess) throw std::runtime_error(cudaGetErrorString(e));
}
template<class T> static T* alloc(size_t n) {
    T* p = nullptr; ck(cudaMalloc((void**)&p, n * sizeof(T))); return p;
}
int main() {
    namespace k = strata::kernels;
    cudaStream_t s; ck(cudaStreamCreate(&s));
    std::mt19937 rng(20261003);
    std::normal_distribution<float> nd(0.f, 0.1f);
    size_t compared = 0, failed = 0;
    for (int n : {2560, 6144}) {
        const int m = 257, ldx = n + 2, ldy = m + 3, cap = strata::kSpecMaxT;
        std::vector<uint16_t> w(size_t(n)*m);
        for (auto& v : w) { float f=nd(rng); uint32_t bits; std::memcpy(&bits,&f,4); v=uint16_t(bits>>16); }
        std::vector<float> x(size_t(ldx)*cap), init(size_t(ldy)*cap, -12345.f);
        for (auto& v : x) v=nd(rng);
        auto dw=alloc<uint16_t>(w.size()); auto dx=alloc<float>(x.size());
        auto dy=alloc<float>(init.size()); auto dz=alloc<float>(init.size());
        ck(cudaMemcpy(dw,w.data(),w.size()*2,cudaMemcpyHostToDevice));
        ck(cudaMemcpy(dx,x.data(),x.size()*4,cudaMemcpyHostToDevice));
        for (int t=1;t<=cap;++t) {
            ck(cudaMemcpy(dy,init.data(),init.size()*4,cudaMemcpyHostToDevice));
            ck(cudaMemcpy(dz,init.data(),init.size()*4,cudaMemcpyHostToDevice));
            k::bf16_gemv_fp32_mmvf_multi(dx,ldx,dw,dy,ldy,n,m,t,s);
            for (int j=0;j<t;++j) k::bf16_gemv_fp32_mmvf(dx+size_t(j)*ldx,dw,dz+size_t(j)*ldy,n,m,s);
            ck(cudaStreamSynchronize(s));
            std::vector<float> a(init.size()),b(init.size());
            ck(cudaMemcpy(a.data(),dy,a.size()*4,cudaMemcpyDeviceToHost));
            ck(cudaMemcpy(b.data(),dz,b.size()*4,cudaMemcpyDeviceToHost));
            size_t diff=0;
            for (size_t i=0;i<a.size();++i) {
                ++compared;
                diff += !std::isfinite(a[i]) || std::memcmp(&a[i],&b[i],4)!=0;
            }
            failed+=diff;
            std::printf("bf16 n=%d T=%d output/tail differences=%zu\n",n,t,diff);
        }
        ck(cudaFree(dw));ck(cudaFree(dx));ck(cudaFree(dy));ck(cudaFree(dz));
    }
    ck(cudaStreamDestroy(s));
    std::printf("wide_bf16_parity: compared=%zu failed=%zu\n",compared,failed);
    return failed ? 1 : 0;
}
