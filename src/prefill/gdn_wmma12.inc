// Included by kernels.cu right after the gfx11 chunked-GDN kernels (it uses their constants, types and helpers).
//
// STRATA_GDN_CHUNKED=1 on gfx12 (RDNA4: R9700 / 9070 / 9060): the same chunked algorithm as the gfx11 kernels above, on
// the gfx12 matrix cores.  The fragment layout differs from gfx11 (wave32, v_wmma_f32_16x16x16_f16; checked on an R9700 by
// results/gdn/GDN-A/micro/wmma12.cpp): A and B take 8 halves a lane, lane l holding row (A) or column (B) l & 15 and
// k = 8 * (l >> 4) + 0..7; the accumulator lane l holds column l & 15 and rows 8 * (l >> 4) + 0..7.  So an accumulator IS the
// next product's B operand (an FP16 conversion only: no permlane / byte permute as on gfx11), and the row of accumulator
// element v is 8 * hi + v (gfx11: 2 * v + hi).  Everything else (chunk of 16, FP16 operands, FP32 accumulate and state, the
// norm fused, T and P from a prep kernel) is the gfx11 design, so the numerics are the same class (FP16 operands).
#if defined(__gfx1200__) || defined(__gfx1201__)
#define STRATA_GDN_WMMA12 1
#endif
__device__ __forceinline__ gw_f8 gw_mma12(gw_h8 a, gw_h8 b, gw_f8 c) {
#if defined(STRATA_GDN_WMMA12)
    return __builtin_amdgcn_wmma_f32_16x16x16_f16_w32_gfx12(a, b, c);
#else
    (void) a; (void) b; (void) c;
    __builtin_trap();   // not a gfx12 device pass: the runtime gate never launches it
#endif
}
__device__ __forceinline__ gw_h8 gw_acc_to_b12(gw_f8 x) {
    gw_h8 r;
#pragma unroll
    for (int i = 0; i < 8; ++i) r[i] = (_Float16) x[i];
    return r;
}
__device__ __forceinline__ gw_h8 gw_ld8(const _Float16* p) { return *reinterpret_cast<const gw_h8*>(p); }   // 16 bytes of LDS

__global__ void __launch_bounds__(32 * GW_VPK) gdn_w12_prep_kernel(const float* __restrict__ h, const float* __restrict__ gate,
                                                                const float* __restrict__ beta, _Float16* __restrict__ tp,
                                                                int64_t T) {
    __shared__ float sa[GW_VPK][GW_CK * GW_CK], sg[GW_VPK][GW_CK], sb[GW_VPK][GW_CK];
    const int qh = blockIdx.x, ch = blockIdx.y, w = threadIdx.x >> 5, l = threadIdx.x & 31, c = l & 15, hi = l >> 4;
    const int vh = qh + w * HK;
    const int64_t t0 = (int64_t) ch * GW_CK;
    gw_f8 kk = {}, qk = {};   // k_t.k_i and q_t.k_i (lane: column i = c, rows t = 8 * hi + v)
    {
        const bool ok = t0 + c < T;   // past the end: zero rows
        const float* ht = h + (ok ? t0 + c : 0) * C;
#pragma unroll
        for (int j = 0; j < S / 16; ++j) {
            gw_h8 ka, qa;
#pragma unroll
            for (int i = 0; i < 2; ++i) {
                const gw_f4 k4 = *reinterpret_cast<const gw_f4*>(ht + HK * S + qh * S + 16 * j + 8 * hi + 4 * i);
                const gw_f4 q4 = *reinterpret_cast<const gw_f4*>(ht + qh * S + 16 * j + 8 * hi + 4 * i);
#pragma unroll
                for (int e = 0; e < 4; ++e) {
                    ka[4 * i + e] = (_Float16) (ok ? k4[e] : 0.0f);
                    qa[4 * i + e] = (_Float16) (ok ? q4[e] : 0.0f);
                }
            }
            kk = gw_mma12(ka, ka, kk);   // B = K^T: lane i holds column i of K^T = row i of K, the A operand itself
            qk = gw_mma12(qa, ka, qk);
        }
    }
    if (l < GW_CK) {   // past the end: gate 0, beta 0
        const bool ok = t0 + l < T;
        float g = ok ? gate[(t0 + l) * HV + vh] : 0.0f;
#pragma unroll
        for (int o = 1; o < GW_CK; o <<= 1) {
            const float u = __shfl_up(g, o, GW_CK);
            if (l >= o) g += u;
        }
        sg[w][l] = g;
        sb[w][l] = ok ? beta[(t0 + l) * HV + vh] : 0.0f;
    }
    __syncthreads();
    _Float16* out = tp + ((int64_t) ch * HV + vh) * (2 * GW_CK * GW_CK);
#pragma unroll
    for (int v = 0; v < 8; ++v) {
        const int t = 8 * hi + v;
        sa[w][t * GW_CK + c] = c < t ? sb[w][t] * __expf(sg[w][t] - sg[w][c]) * kk[v] : 0.0f;
        out[GW_CK * GW_CK + t * GW_CK + c] = (_Float16) (c <= t ? __expf(sg[w][t] - sg[w][c]) * qk[v] : 0.0f);
    }
    __syncthreads();
    if (l < GW_CK) {   // lane c: column c of T = (I + A)^-1 by forward substitution
        float tc[GW_CK];
#pragma unroll
        for (int t = 0; t < GW_CK; ++t) {
            float v = t == c ? 1.0f : 0.0f;
#pragma unroll
            for (int k = 0; k < t; ++k) v = fmaf(-sa[w][t * GW_CK + k], tc[k], v);
            tc[t] = v;
            out[t * GW_CK + c] = (_Float16) v;
        }
    }
}

__global__ void __launch_bounds__(GW_NW * 32) gdn_w12_scan_kernel(float* __restrict__ state, const float* __restrict__ h,
                                                                  const float* __restrict__ gate, const float* __restrict__ beta,
                                                                  const float* __restrict__ z, const float* __restrict__ gamma,
                                                                  const unsigned* __restrict__ tp, float eps,
                                                                  uint16_t* __restrict__ y16, int64_t T, int64_t ld16) {
    __shared__ __attribute__((aligned(16))) _Float16 sk[GW_CK * GW_KP], sq[GW_CK * GW_KP], skt[S * GW_CK],
        stp[2 * GW_CK * GW_CK];
    __shared__ __attribute__((aligned(16))) float sv[GW_CK * S], so[GW_CK * S], sn[GW_CK * GW_NW];
    __shared__ float sg[GW_CK], sb[GW_CK], sgam[S];
    const _Float16 *st_ = stp, *sp_ = stp + GW_CK * GW_CK;   // T, P
    const int vh = blockIdx.x, qh = vh % HK, w = threadIdx.x >> 5, l = threadIdx.x & 31, c = l & 15, hi = l >> 4;
    const int col = 16 * w + c;
    const int st = threadIdx.x >> 4, sr = (threadIdx.x & 15) * 8;
    const size_t rs = (size_t) HV * S;
    gw_f8 s[S / 16];   // the state: rows 16j + 8 * hi + v, column col
#pragma unroll
    for (int j = 0; j < S / 16; ++j)
#pragma unroll
        for (int v = 0; v < 8; ++v) s[j][v] = state[(size_t) (16 * j + 8 * hi + v) * rs + (size_t) vh * S + col];
    if (threadIdx.x < S) sgam[threadIdx.x] = gamma[threadIdx.x];
    const float out_scale = rsqrtf((float) S);
    GwChunk cur;
    gw_load(cur, h, gate, beta, tp, 0, T, vh, qh);
    unsigned touched = 0;
    gw_f4 z0 = {}, z1 = {};
    auto store_rows = [&](int64_t c0) {
        if (c0 + st >= T) return;
        const float* o = &so[st * S + sr];
        gw_h8 r;
#pragma unroll
        for (int i = 0; i < 8; ++i) r[i] = (_Float16) (o[i] * sigm(i < 4 ? z0[i] : z1[i - 4]));
        *reinterpret_cast<uint4*>(y16 + (c0 + st) * ld16 + vh * S + sr) = __builtin_bit_cast(uint4, r);
    };
    for (int64_t t0 = 0; t0 < T; t0 += GW_CK) {
        {   // stage this chunk
            gw_h8 kh, qq;
#pragma unroll
            for (int i = 0; i < 8; ++i) {
                kh[i] = (_Float16) (i < 4 ? cur.k0[i] : cur.k1[i - 4]);
                qq[i] = (_Float16) (i < 4 ? cur.q0[i] : cur.q1[i - 4]);
                skt[(sr + i) * GW_CK + st] = kh[i];
            }
            *reinterpret_cast<uint4*>(&sk[st * GW_KP + sr]) = __builtin_bit_cast(uint4, kh);
            *reinterpret_cast<uint4*>(&sq[st * GW_KP + sr]) = __builtin_bit_cast(uint4, qq);
            *reinterpret_cast<gw_f4*>(&sv[st * S + sr]) = cur.v0;
            *reinterpret_cast<gw_f4*>(&sv[st * S + sr + 4]) = cur.v1;
            reinterpret_cast<unsigned*>(stp)[threadIdx.x] = cur.tp;
            if (threadIdx.x < GW_CK) {   // past the end: gate 0, beta 0
                const bool ok = t0 + l < T;
                float g = ok ? cur.g : 0.0f;
#pragma unroll
                for (int o = 1; o < GW_CK; o <<= 1) {
                    const float u = __shfl_up(g, o, GW_CK);
                    if (l >= o) g += u;
                }
                sg[l] = g;
                sb[l] = ok ? cur.b : 0.0f;
            }
        }
        if (t0 + GW_CK < T) gw_load(cur, h, gate, beta, tp, t0 + GW_CK, T, vh, qh);
        const unsigned touch_now = gw_touch(h, z, t0 + GW_AHEAD * GW_CK, T, vh, qh);
        __syncthreads();   // (1) this chunk staged; the previous chunk's norm in so
        if (t0 > 0) store_rows(t0 - GW_CK);
        __asm__ volatile("" ::"v"(touched));
        touched = touch_now;
        {
            const int64_t tz = std::min<int64_t>(t0 + st, T - 1);
            z0 = *reinterpret_cast<const gw_f4*>(z + tz * HV * S + vh * S + sr);
            z1 = *reinterpret_cast<const gw_f4*>(z + tz * HV * S + vh * S + sr + 4);
        }
        gw_f8 x = {}, qs = {};   // K S0 and Q S0, this wave's columns
#pragma unroll
        for (int j = 0; j < S / 16; ++j) {
            const gw_h8 b = gw_acc_to_b12(s[j]);
            x = gw_mma12(gw_ld8(sk + c * GW_KP + 16 * j + 8 * hi), b, x);
            qs = gw_mma12(gw_ld8(sq + c * GW_KP + 16 * j + 8 * hi), b, qs);
        }
        gw_f8 y;
#pragma unroll
        for (int v = 0; v < 8; ++v) {
            const int t = 8 * hi + v;
            y[v] = sb[t] * (sv[t * S + col] - __expf(sg[t]) * x[v]);
        }
        const gw_f8 d = gw_mma12(gw_ld8(st_ + c * GW_CK + 8 * hi), gw_acc_to_b12(y), gw_f8{});
        gw_f8 o;
#pragma unroll
        for (int v = 0; v < 8; ++v) o[v] = __expf(sg[8 * hi + v]) * qs[v];
        o = gw_mma12(gw_ld8(sp_ + c * GW_CK + 8 * hi), gw_acc_to_b12(d), o);
#pragma unroll
        for (int v = 0; v < 8; ++v) {
            o[v] *= out_scale;
            float p = o[v] * o[v];
#pragma unroll
            for (int m = 1; m < 16; m <<= 1) p += __shfl_xor(p, m);
            if (c == 0) sn[(8 * hi + v) * GW_NW + w] = p;
        }
        const float gl = sg[GW_CK - 1];
        gw_f8 dd;
#pragma unroll
        for (int v = 0; v < 8; ++v) dd[v] = __expf(gl - sg[8 * hi + v]) * d[v];
        const gw_h8 db = gw_acc_to_b12(dd);
        const float eg = __expf(gl);
#pragma unroll
        for (int j = 0; j < S / 16; ++j) s[j] = gw_mma12(gw_ld8(skt + (16 * j + c) * GW_CK + 8 * hi), db, s[j] * eg);
        __syncthreads();   // (2) the sums of o^2
        const float g_col = sgam[col];
#pragma unroll
        for (int v = 0; v < 8; ++v) {
            const int t = 8 * hi + v;
            const gw_f4 n0 = *reinterpret_cast<const gw_f4*>(&sn[t * GW_NW]), n1 = *reinterpret_cast<const gw_f4*>(&sn[t * GW_NW + 4]);
            const float ss = n0[0] + n0[1] + n0[2] + n0[3] + n1[0] + n1[1] + n1[2] + n1[3];
            so[t * S + col] = o[v] * rsqrtf(ss * (1.0f / S) + eps) * g_col;
        }
    }
    __asm__ volatile("" ::"v"(touched));
    __syncthreads();
    store_rows((T - 1) / GW_CK * GW_CK);
    __asm__ volatile("" : "+s"(state));
#pragma unroll
    for (int j = 0; j < S / 16; ++j)
#pragma unroll
        for (int v = 0; v < 8; ++v) state[(size_t) (16 * j + 8 * hi + v) * rs + (size_t) vh * S + col] = s[j][v];
}
