// BF16/F16 prefill through the actual engine GEMM path against a CPU reference.
#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include "strata/kernels/bf16_bits.hpp"
#include "strata/prefill/gemm.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>

#define CHECK(call) do { const auto e = (call); if (e != cudaSuccess) { \
    std::fprintf(stderr, "%s: %s\n", #call, cudaGetErrorString(e)); std::exit(2); } } while (0)

struct Buffer {
    void* p = nullptr;
    explicit Buffer(size_t bytes) { CHECK(cudaMalloc(&p, bytes)); }
    ~Buffer() { if (p) (void) cudaFree(p); }
};

bool run(strata::prefill::Gemm& gemm, cudaStream_t stream, bool bf16,
         int t, int n, int k, int ldy, float beta, float scale=1.0f) {
    std::mt19937 rng(51012 + t + n);
    std::uniform_real_distribution<float> dist(-0.25f, 0.25f);
    std::vector<uint16_t> x((size_t)t*k), w((size_t)n*k);
    std::vector<float> xf(x.size()), wf(w.size());
    auto fill = [&](auto& bits, auto& values) {
        for (size_t i = 0; i < bits.size(); ++i) {
            if (bf16) {
                const uint16_t v = strata::kernels::bf16_from_f32(dist(rng)*scale);
                bits[i] = v;
                const uint32_t wide = static_cast<uint32_t>(v) << 16;
                std::memcpy(&values[i], &wide, 4);
            } else {
                const __half v = __float2half_rn(dist(rng));
                std::memcpy(&bits[i], &v, 2);
                values[i] = __half2float(v);
            }
        }
    };
    fill(x, xf); fill(w, wf);
    constexpr int offset = 5;
    std::vector<float> initial(offset + (size_t)t*ldy + 8, -777.25f);
    for (int r = 0; r < t; ++r) for (int c = 0; c < n; ++c)
        initial[offset + (size_t)r*ldy + c] = (r+c)%17 * 0.03125f;
    Buffer dx(x.size()*2), dw(w.size()*2), dy(initial.size()*4);
    CHECK(cudaMemcpyAsync(dx.p,x.data(),x.size()*2,cudaMemcpyHostToDevice,stream));
    CHECK(cudaMemcpyAsync(dw.p,w.data(),w.size()*2,cudaMemcpyHostToDevice,stream));
    CHECK(cudaMemcpyAsync(dy.p,initial.data(),initial.size()*4,cudaMemcpyHostToDevice,stream));
    if (bf16) gemm.bf16((const uint16_t*)dx.p,(const uint16_t*)dw.p,(float*)dy.p+offset,t,n,k,ldy,beta);
    else gemm.f16((const uint16_t*)dx.p,(const uint16_t*)dw.p,(float*)dy.p+offset,t,n,k,ldy,beta);
    CHECK(cudaStreamSynchronize(stream));
    std::vector<float> got(initial.size());
    CHECK(cudaMemcpy(got.data(),dy.p,got.size()*4,cudaMemcpyDeviceToHost));
    std::vector<bool> active(got.size());
    double diff2=0, ref2=0, maximum=0, reference_max=0;
    bool ok=true;
    for (int r=0;r<t;++r) for (int c=0;c<n;++c) {
        const size_t j=offset+(size_t)r*ldy+c;
        active[j]=true;
        double ref=beta*initial[j];
        for (int i=0;i<k;++i) ref+=(double)xf[(size_t)r*k+i]*wf[(size_t)c*k+i];
        reference_max=std::max(reference_max,std::abs(ref));
        const double d=(double)got[j]-ref;
        ok=ok && std::isfinite(got[j]);
        diff2+=d*d; ref2+=ref*ref; maximum=std::max(maximum,std::abs(d));
    }
    for (size_t j=0;j<got.size();++j) if (!active[j]) ok=ok && got[j]==initial[j];
    const double rel=std::sqrt(diff2/std::max(ref2,1e-300));
    ok=ok && rel<1e-4 && maximum<5e-3+1e-5*reference_max;
    std::printf("%s %s T=%d N=%d K=%d ldy=%d beta=%.1f rel_l2=%.3g max_abs=%.3g\n",
                ok?"PASS":"FAIL",bf16?"BF16":"F16",t,n,k,ldy,beta,rel,maximum);
    return ok;
}

int main() {
    setvbuf(stdout,nullptr,_IONBF,0);
    cudaStream_t stream;
    CHECK(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));
    bool ok=true;
    {
        strata::prefill::Gemm gemm;
        std::string error;
        if (!gemm.init(stream,0,error)) { std::fprintf(stderr,"%s\n",error.c_str()); return 2; }
        ok=run(gemm,stream,true,16,96,2560,96,0) && ok;
        ok=run(gemm,stream,true,3,7,13,11,0,1048576.0f) && ok;
        ok=run(gemm,stream,true,513,7,8192,11,-0.5f) && ok;
        ok=run(gemm,stream,false,3,513,8192,517,1) && ok;
        ok=run(gemm,stream,true,17,48,2560,64,1) && ok;
        ok=run(gemm,stream,false,32,640,2560,648,0) && ok;
        ok=run(gemm,stream,false,64,2560,640,2560,1) && ok;
    }
    {
        Buffer workspace(32u<<20);
        strata::prefill::Gemm external;
        std::string error;
        if (!external.init_external(stream,nullptr,0,workspace.p,32u<<20,error)) {
            std::fprintf(stderr,"%s\n",error.c_str()); return 2;
        }
        ok=run(external,stream,true,17,23,513,29,-0.5f) && ok;
        external.rebind(nullptr,0,workspace.p,32u<<20);
        ok=run(external,stream,false,31,17,257,23,1) && ok;
    }
    CHECK(cudaStreamDestroy(stream));
    return ok?0:1;
}
