// Included by kernels.cu after gdn_wmma12.inc.  The gfx12 chunked GDN with the causal conv + SiLU + q/k L2 norm folded in:
// the two kernels read the conv's RAW input (the qkv projection, plus the 3-token history in front of the first token) and
// no h buffer is written or read back (41 KB a token in each direction at 10240 FP32 channels).  The arithmetic is the
// unfused path's: the conv in FP32 (four taps, SiLU), the q/k heads normalised with rsqrtf(sum + eps) before their FP16
// rounding for the matrix cores, v kept FP32.  The history is rewritten afterwards by gdn_conv_hist_kernel.
//   prep: block (key head, chunk): the 16 tokens' q and k conv'd into LDS (cooperatively, once for the three value heads),
//         normalised, then the gdn_w12_prep_kernel body reading its A / B operands from LDS.
//   scan: block per value head; per chunk the 19 raw rows (3 history + 16) of its q, k and v channels are staged in LDS
//         (a chunk ahead in registers), k / q conv'd and normalised into the FP16 operands, v conv'd where it is used.
#if defined(__HIPCC__)
constexpr int GF_ROWS = GW_CK + 3;           // raw rows of a chunk: 3 history + 16
constexpr int GF_RS = 3 * S + 4;             // the scan's raw row stride (q | k | v), floats
constexpr int GF_RAWV = (GF_ROWS * 3 * S / 4 + 255) / 256;   // f4 slots a thread keeps for the next chunk: 8
__device__ __forceinline__ float gf_silu(float s) { return s / (1.0f + __expf(-s)); }

__global__ void __launch_bounds__(128) gdn_w12f_prep_kernel(const float* __restrict__ hist, const float* __restrict__ qkv,
                                                           const float* __restrict__ cw, const float* __restrict__ gate,
                                                           const float* __restrict__ beta, _Float16* __restrict__ tp, int64_t T,
                                                           float eps) {
    constexpr int RS = 2 * S + 1;   // padded LDS row (q 0..127, k 128..255)
    __shared__ float sc[GW_CK * RS];
    __shared__ float sinv[GW_CK][2];
    __shared__ float sa[GW_VPK][GW_CK * GW_CK], sg[GW_VPK][GW_CK], sb[GW_VPK][GW_CK];
    const int qh = blockIdx.x, ch = blockIdx.y, tid = threadIdx.x, w = tid >> 5, l = tid & 31, c = l & 15, hi = l >> 4;
    const int64_t t0 = (int64_t) ch * GW_CK;
    for (int idx = tid; idx < GW_CK * 2 * S; idx += 128) {   // conv + SiLU of the 16 tokens x 256 channels (coalesced)
        const int tt = idx >> 8, cc = idx & 255;
        const int chn = cc < S ? qh * S + cc : HK * S + qh * S + (cc - S);
        const int64_t t = t0 + tt;
        float v = 0.0f;
        if (t < T) {
            const float4 wv = *reinterpret_cast<const float4*>(cw + (size_t) chn * 4);
            auto in = [&](int64_t u) -> float { return u >= 0 ? qkv[u * C + chn] : hist[chn * 3 + (int) (u + 3)]; };
            const float s = in(t - 3) * wv.x + in(t - 2) * wv.y + in(t - 1) * wv.z + in(t) * wv.w;
            v = gf_silu(s);
        }
        sc[tt * RS + cc] = v;
    }
    __syncthreads();
    if (tid < 2 * GW_CK) {   // token tid >> 1, part tid & 1 (0 = q, 1 = k): the head's sum of squares
        const float* r = sc + (tid >> 1) * RS + (tid & 1) * S;
        float ss = 0.0f;
        for (int i = 0; i < S; ++i) ss = fmaf(r[i], r[i], ss);
        sinv[tid >> 1][tid & 1] = rsqrtf(ss + eps);
    }
    __syncthreads();
    const bool act = w < GW_VPK;   // the fourth wave only helped with the conv; it still takes every barrier
    const int vh = qh + w * HK;
    gw_f8 kk = {}, qk = {};
    if (act) {
        const float ik = sinv[c][1], iq = sinv[c][0];
#pragma unroll
        for (int j = 0; j < S / 16; ++j) {
            gw_h8 ka, qa;
#pragma unroll
            for (int e = 0; e < 8; ++e) {
                ka[e] = (_Float16) (sc[c * RS + S + 16 * j + 8 * hi + e] * ik);
                qa[e] = (_Float16) (sc[c * RS + 16 * j + 8 * hi + e] * iq);
            }
            kk = gw_mma12(ka, ka, kk);
            qk = gw_mma12(qa, ka, qk);
        }
    }
    if (act && l < GW_CK) {
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
    if (act) {
#pragma unroll
        for (int v = 0; v < 8; ++v) {
            const int t = 8 * hi + v;
            sa[w][t * GW_CK + c] = c < t ? sb[w][t] * __expf(sg[w][t] - sg[w][c]) * kk[v] : 0.0f;
            out[GW_CK * GW_CK + t * GW_CK + c] = (_Float16) (c <= t ? __expf(sg[w][t] - sg[w][c]) * qk[v] : 0.0f);
        }
    }
    __syncthreads();
    if (act && l < GW_CK) {
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

// The raw rows of the chunk at t0 (rows t0 - 3 .. t0 + 15 of the qkv projection; rows before the prompt come from the
// history; rows past the end repeat the last row: finite, their gate and beta are 0), 8 f4 a thread, and its gate / beta.
struct GfChunk {
    gw_f4 raw[GF_RAWV];
    float g, b;
    unsigned tp;
};
__device__ __forceinline__ void gf_load(GfChunk& in, const float* __restrict__ hist, const float* __restrict__ qkv,
                                        const float* __restrict__ gate, const float* __restrict__ beta,
                                        const unsigned* __restrict__ tp, int64_t t0, int64_t T, int vh, int qh) {
    in.tp = tp[((t0 / GW_CK) * HV + vh) * (GW_CK * GW_CK) + threadIdx.x];
#pragma unroll
    for (int m = 0; m < GF_RAWV; ++m) {
        const int idx = threadIdx.x + 256 * m;
        gw_f4 r = {};
        if (idx < GF_ROWS * 96) {
            const int row = idx / 96, f = idx % 96, seg = f >> 5, within = (f & 31) * 4;
            const int chn = (seg == 0 ? qh * S : seg == 1 ? HK * S + qh * S : 2 * HK * S + vh * S) + within;
            const int64_t t = t0 - 3 + row;
            if (t >= 0) {
                r = *reinterpret_cast<const gw_f4*>(qkv + std::min<int64_t>(t, T - 1) * C + chn);
            } else {
#pragma unroll
                for (int e = 0; e < 4; ++e) r[e] = hist[(chn + e) * 3 + (int) (t + 3)];
            }
        }
        in.raw[m] = r;
    }
    if (threadIdx.x < GW_CK) {
        const int64_t tl = std::min<int64_t>(t0 + threadIdx.x, T - 1);
        in.g = gate[tl * HV + vh];
        in.b = beta[tl * HV + vh];
    }
}
// the cache warm-up of a later chunk: this block's q, k, v rows (96 f4 lines of 128 bytes each... one line a thread) and z
__device__ __forceinline__ unsigned gf_touch(const float* __restrict__ qkv, const float* __restrict__ z, int64_t t0, int64_t T,
                                             int vh, int qh) {
    const int t = threadIdx.x >> 4, part = threadIdx.x & 15, kind = part >> 2;
    if (t0 + t >= T) return 0u;
    const float* p = kind == 0 ? qkv + (t0 + t) * C + HK * S + qh * S
                   : kind == 1 ? qkv + (t0 + t) * C + qh * S
                   : kind == 2 ? qkv + (t0 + t) * C + 2 * HK * S + vh * S
                               : z + (t0 + t) * HV * S + vh * S;
    return __float_as_uint(p[32 * (part & 3)]);
}

template<bool LB>
__global__ void __launch_bounds__(GW_NW * 32) gdn_w12f_scan_kernel(float* __restrict__ state, const float* __restrict__ hist,
                                                                   const float* __restrict__ qkv, const float* __restrict__ cw,
                                                                   const float* __restrict__ gate, const float* __restrict__ beta,
                                                                   const float* __restrict__ z, const float* __restrict__ gamma,
                                                                   const unsigned* __restrict__ tp, float eps, float l2eps,
                                                                   uint16_t* __restrict__ y16, int64_t T, int64_t ld16) {
    __shared__ __attribute__((aligned(16))) _Float16 sk[GW_CK * GW_KP], sq[GW_CK * GW_KP], skt[S * GW_CK], stp[2 * GW_CK * GW_CK];
    __shared__ __attribute__((aligned(16))) float sraw[GF_ROWS * GF_RS], so[GW_CK * S], sn[GW_CK * GW_NW], swq[2 * S * 4];
    __shared__ float sg[GW_CK], sb[GW_CK], sgam[S];
    const _Float16 *st_ = stp, *sp_ = stp + GW_CK * GW_CK;
    const int vh = blockIdx.x, qh = vh % HK, w = threadIdx.x >> 5, l = threadIdx.x & 31, c = l & 15, hi = l >> 4;
    const int col = 16 * w + c;
    const int st = threadIdx.x >> 4, sr = (threadIdx.x & 15) * 8;
    const size_t rs = (size_t) HV * S;
    gw_f8 s[S / 16];
#pragma unroll
    for (int j = 0; j < S / 16; ++j)
#pragma unroll
        for (int v = 0; v < 8; ++v) s[j][v] = state[(size_t) (16 * j + 8 * hi + v) * rs + (size_t) vh * S + col];
    if (threadIdx.x < S) sgam[threadIdx.x] = gamma[threadIdx.x];
    {   // the q and k conv weights of this head's channels (q 0..127, k 128..255), and this lane's v column
        for (int i = threadIdx.x; i < 2 * S; i += 256)
            *reinterpret_cast<float4*>(&swq[i * 4]) =
                *reinterpret_cast<const float4*>(cw + (size_t) (i < S ? qh * S + i : HK * S + qh * S + (i - S)) * 4);
    }
    const float4 wvv = *reinterpret_cast<const float4*>(cw + (size_t) (2 * HK * S + vh * S + col) * 4);
    const float out_scale = rsqrtf((float) S);
    GfChunk cur;
    gf_load(cur, hist, qkv, gate, beta, tp, 0, T, vh, qh);
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
        {   // this chunk's raw rows to LDS (the previous chunk's reads of them ended before its barrier (2)), T / P, gates
#pragma unroll
            for (int m = 0; m < GF_RAWV; ++m) {
                const int idx = threadIdx.x + 256 * m;
                if (idx < GF_ROWS * 96) {
                    const int row = idx / 96, f = idx % 96;
                    *reinterpret_cast<gw_f4*>(&sraw[row * GF_RS + f * 4]) = cur.raw[m];
                }
            }
            reinterpret_cast<unsigned*>(stp)[threadIdx.x] = cur.tp;
            if (threadIdx.x < GW_CK) {
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
        if (t0 + GW_CK < T) gf_load(cur, hist, qkv, gate, beta, tp, t0 + GW_CK, T, vh, qh);
        const unsigned touch_now = gf_touch(qkv, z, t0 + GW_AHEAD * GW_CK, T, vh, qh);
        gw12_barrier<LB>();   // (A) raw rows staged
        {   // k and q of token st: conv + SiLU on the thread's 8 channels, the head's sum of squares over the 16 lanes
            gw_h8 kh, qq;
            float ssk = 0.0f, ssq = 0.0f, kv[8], qv[8];
#pragma unroll
            for (int e = 0; e < 8; ++e) {
                const float4 wq = *reinterpret_cast<const float4*>(&swq[(sr + e) * 4]);
                const float4 wk = *reinterpret_cast<const float4*>(&swq[(S + sr + e) * 4]);
                const float* rq = &sraw[st * GF_RS + sr + e];
                const float* rk = rq + S;
                const float sq_ = rq[0] * wq.x + rq[GF_RS] * wq.y + rq[2 * GF_RS] * wq.z + rq[3 * GF_RS] * wq.w;
                const float sk_ = rk[0] * wk.x + rk[GF_RS] * wk.y + rk[2 * GF_RS] * wk.z + rk[3 * GF_RS] * wk.w;
                qv[e] = gf_silu(sq_);
                kv[e] = gf_silu(sk_);
                ssq = fmaf(qv[e], qv[e], ssq);
                ssk = fmaf(kv[e], kv[e], ssk);
            }
#pragma unroll
            for (int m = 1; m < 16; m <<= 1) {
                ssq += __shfl_xor(ssq, m);
                ssk += __shfl_xor(ssk, m);
            }
            const float iq = rsqrtf(ssq + l2eps), ik = rsqrtf(ssk + l2eps);
#pragma unroll
            for (int e = 0; e < 8; ++e) {
                kh[e] = (_Float16) (kv[e] * ik);
                qq[e] = (_Float16) (qv[e] * iq);
                skt[(sr + e) * GW_CK + st] = kh[e];
            }
            *reinterpret_cast<uint4*>(&sk[st * GW_KP + sr]) = __builtin_bit_cast(uint4, kh);
            *reinterpret_cast<uint4*>(&sq[st * GW_KP + sr]) = __builtin_bit_cast(uint4, qq);
        }
        gw12_barrier<LB>();   // (B) k / q / T / P / gates staged; the previous chunk's norm in so
        if (t0 > 0) store_rows(t0 - GW_CK);
        __asm__ volatile("" ::"v"(touched));
        touched = touch_now;
        {
            const int64_t tz = std::min<int64_t>(t0 + st, T - 1);
            z0 = *reinterpret_cast<const gw_f4*>(z + tz * HV * S + vh * S + sr);
            z1 = *reinterpret_cast<const gw_f4*>(z + tz * HV * S + vh * S + sr + 4);
        }
        gw_f8 x = {}, qs = {};
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
            const float* rv = &sraw[t * GF_RS + 2 * S + col];   // raw v rows t .. t + 3 (token t - 3 .. t of the conv)
            const float sv_ = rv[0] * wvv.x + rv[GF_RS] * wvv.y + rv[2 * GF_RS] * wvv.z + rv[3 * GF_RS] * wvv.w;
            y[v] = sb[t] * (gf_silu(sv_) - __expf(sg[t]) * x[v]);
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
        gw12_barrier<LB>();   // (2) the sums of o^2; every read of this chunk's raw rows is done
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
    gw12_barrier<LB>();
    store_rows((T - 1) / GW_CK * GW_CK);
    __asm__ volatile("" : "+s"(state));
#pragma unroll
    for (int j = 0; j < S / 16; ++j)
#pragma unroll
        for (int v = 0; v < 8; ++v) state[(size_t) (16 * j + 8 * hi + v) * rs + (size_t) vh * S + col] = s[j][v];
}
#endif   // __HIPCC__
