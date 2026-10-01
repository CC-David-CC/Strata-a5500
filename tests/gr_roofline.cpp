#include "strata/kernels/fused_gr.hpp"
#include <cuda_runtime.h>
#include <vector>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <cstdint>
#define CK(x) do { auto e=(x); if(e!=cudaSuccess){fprintf(stderr,"%s\n",cudaGetErrorString(e));exit(2);} } while(0)
template<class T> T* upload(const std::vector<T>& v){T* p;CK(cudaMalloc((void**)&p,v.size()*sizeof(T)));CK(cudaMemcpy(p,v.data(),v.size()*sizeof(T),cudaMemcpyHostToDevice));return p;}
int main(){
 using namespace strata::kernels;
 setvbuf(stdout,nullptr,_IONBF,0);
 constexpr int D=10240,N=2560,L=320,S=4;
 std::vector<uint16_t> w(D*L),inj(D*4);
 uint32_t seed=73;
 auto random=[&](){seed=1664525u*seed+1013904223u;return (float(int(seed>>8)%2001)-1000)/1000.0f;};
 for(auto& x:w){float f=random()*.025f;uint32_t b;memcpy(&b,&f,4);x=b>>16;}
 for(auto& x:inj){float f=random()*.025f;uint32_t b;memcpy(&b,&f,4);x=b>>16;}
 auto wd=upload(w);auto wu=upload(w);auto wi=upload(inj);
 std::vector<float> norm(D);for(auto& x:norm)x=1+random()*.1f;auto wn=upload(norm);
 std::vector<float> inputs(8*(D+N+4));for(auto& x:inputs)x=random();auto input=upload(inputs);
 constexpr int O=D+L+4+4+N;
 std::vector<float> zeros(8*O);auto out=upload(zeros);
 std::vector<float> scratch(8*D);auto xn=upload(scratch);
 int failures=0;cudaEvent_t begin,end;CK(cudaEventCreate(&begin));CK(cudaEventCreate(&end));
 for(const char* hc:{"0","1","2"}) {
 setenv("STRATA_HC_SPLIT",hc,1);
 for(int T=1;T<=8;T++)for(int apply=0;apply<2;apply++)for(int inject=0;inject<2;inject++){
  FusedGrArgs a[8];for(int t=0;t<T;t++){
   auto& q=a[t];q.R=input+t*(D+N+4);q.bo_prev=q.R+D;q.inj_prev=q.bo_prev+N;
   q.apply=apply;q.w_norm=wn;q.w_down=wd;q.w_up=wu;q.w_inject=inject?wi:nullptr;
   q.R_out=out+t*O;q.lo=q.R_out+D;q.rs=q.lo+L;q.inject_out=q.rs+4;q.mixed=q.inject_out+4;
  }
  std::vector<float> reference;
  for(const char* mode:{"baseline","max4"}){
   setenv("STRATA_GR_DOWN_MAX4",mode[0]=='m'?"1":"0",1);CK(cudaMemset(out,0xa5,zeros.size()*4));
   fused_gr_read_multi(a,T,xn,nullptr);CK(cudaDeviceSynchronize());
   std::vector<float> got(zeros.size());CK(cudaMemcpy(got.data(),out,got.size()*4,cudaMemcpyDeviceToHost));
   if(mode[0]=='b')reference=got;
   bool ok=memcmp(reference.data(),got.data(),got.size()*4)==0;
   for(int t=0;t<T;t++)for(int j=D;j<O;j++)if(j<D+L+4 || j>=D+L+8 || inject)ok &= std::isfinite(got[t*O+j]);
   failures+=!ok;
   CK(cudaEventRecord(begin));for(int i=0;i<50;i++)fused_gr_read_multi(a,T,xn,nullptr);
   CK(cudaEventRecord(end));CK(cudaEventSynchronize(end));float ms;CK(cudaEventElapsedTime(&ms,begin,end));
   printf("hc=%s T=%d apply=%d inject=%d mode=%s us=%.3f parity=%s\n",hc,T,apply,inject,mode,ms*1000/50,ok?"pass":"FAIL");
  }
 }
 }
 printf("failures=%d\n",failures);return failures?1:0;
}
