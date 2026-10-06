#include "native_prefill_bridge.cu"

__global__ void pack_compact_bf16(const float* src, __nv_bfloat16* dst, const int32_t* map,
                                 int cols, int64_t count) {
    int64_t i=static_cast<int64_t>(blockIdx.x)*blockDim.x+threadIdx.x;
    if(i>=count)return;
    int row=i/cols,k=i%cols,original=map[row];
    dst[i]=__float2bfloat16_rn(original>=0?src[static_cast<int64_t>(original)*cols+k]:0.0f);
}
__global__ void activate_compact_bf16(const __nv_bfloat16* gu,__nv_bfloat16* h,const int32_t* map,
                                     int64_t count) {
    int64_t i=static_cast<int64_t>(blockIdx.x)*blockDim.x+threadIdx.x;
    if(i>=count)return;
    int row=i/640,k=i%640;
    if(map[row]<0){h[i]=__float2bfloat16_rn(0.0f);return;}
    float g=__bfloat162float(gu[static_cast<int64_t>(row)*1280+k]);
    float u=__bfloat162float(gu[static_cast<int64_t>(row)*1280+640+k]);
    h[i]=__float2bfloat16_rn(g/(1.0f+__expf(-g))*u);
}
__global__ void unpack_compact_f32(const __nv_bfloat16* src,float* dst,const int32_t* map,
                                   int cols,int64_t count) {
    int64_t i=static_cast<int64_t>(blockIdx.x)*blockDim.x+threadIdx.x;
    if(i>=count)return;
    int row=i/cols,k=i%cols,original=map[row];
    if(original>=0)dst[static_cast<int64_t>(original)*cols+k]=__bfloat162float(src[i]);
}
extern "C" void compact_pack(const float* src,void* dst,const int32_t* map,int rows,int cols,void* stream){
    int64_t n=static_cast<int64_t>(rows)*cols;
    pack_compact_bf16<<<(n+255)/256,256,0,static_cast<cudaStream_t>(stream)>>>(src,static_cast<__nv_bfloat16*>(dst),map,cols,n);
}
extern "C" void compact_activation(const void* gu,void* h,const int32_t* map,int rows,void* stream){
    int64_t n=static_cast<int64_t>(rows)*640;
    activate_compact_bf16<<<(n+255)/256,256,0,static_cast<cudaStream_t>(stream)>>>(
        static_cast<const __nv_bfloat16*>(gu),static_cast<__nv_bfloat16*>(h),map,n);
}
extern "C" void compact_unpack(const void* src,float* dst,const int32_t* map,int rows,int cols,void* stream){
    int64_t n=static_cast<int64_t>(rows)*cols;
    unpack_compact_f32<<<(n+255)/256,256,0,static_cast<cudaStream_t>(stream)>>>(
        static_cast<const __nv_bfloat16*>(src),dst,map,cols,n);
}
