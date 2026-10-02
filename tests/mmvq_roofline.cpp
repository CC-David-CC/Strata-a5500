// Real dense GGUF tensors: single-column oracle vs multi-column kernel.
// Timings are warm-cache microbenchmarks, NOT measured DRAM bandwidth.
#include "strata/artifact/gguf_reader.hpp"
#include "strata/kernels/native_mmvq.hpp"
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <random>
#include <algorithm>
#include <set>
#include <tuple>
using namespace strata::kernels;
static void ck(cudaError_t e) { if(e!=cudaSuccess){fprintf(stderr,"GPU: %s\n",cudaGetErrorString(e));exit(2);} }
int main(int argc,char**argv) {
 if(argc<2 || argc>3)return 2;
 const bool all_shapes=argc==3 && std::string(argv[2])=="--all-shapes";
 if(argc==3 && !all_shapes)return 2;
 setvbuf(stdout,nullptr,_IONBF,0);
 strata::GgufFile file(argv[1]); cudaStream_t s;ck(cudaStreamCreate(&s));
 int tested=0,failed=0;
 std::set<std::tuple<int,int,int>> seen;
 for(const auto&t:file.tensors()) {
  if(!all_shapes && t.name.rfind("blk.0.",0)!=0 && t.name.rfind("blk.3.",0)!=0)continue;
  if(t.name.find("exps")!=std::string::npos)continue;
  const int type=(int)t.type;
  if(type!=2&&type!=6&&type!=8&&type!=11&&type!=12&&type!=13&&type!=14&&type!=20&&type!=23&&type!=42)continue;
  if(t.shape.size()!=2)continue;
  int ni=(int)t.shape[0],no=(int)t.shape[1];
  const int block=type==42?64:(type==2||type==6||type==8||type==20)?32:256;
  if(ni%block || no<1)continue;
  // Include the ~497 MiB native output head as well as the layer matrices.
  // The test loads only one tensor at a time, including on an 8 GiB card.
  size_t bytes=native_mmvq_weight_bytes(type,ni,no);if(bytes>1024u*1024*1024)continue;
  if(all_shapes && !seen.emplace(type,ni,no).second)continue;
  void*w;float*x,*y,*ref;void*q;
  ck(cudaMalloc(&w,bytes));ck(cudaMemcpy(w,file.tensor_data(t),bytes,cudaMemcpyHostToDevice));
  ck(cudaMalloc((void**)&x,8*ni*sizeof(float)));ck(cudaMalloc(&q,native_q8_1_bytes(ni,8)));
  ck(cudaMalloc((void**)&y,8*no*sizeof(float)));ck(cudaMalloc((void**)&ref,8*no*sizeof(float)));
  std::vector<float> hx(8*ni);std::mt19937 rng(71);std::uniform_real_distribution<float>d(-1,1);for(auto&v:hx)v=d(rng);
  ck(cudaMemcpy(x,hx.data(),hx.size()*sizeof(float),cudaMemcpyHostToDevice));native_quantize_q8_1(x,q,ni,8,s);
  for(int n:{2,3,4,5,6,7,8}) {
   for(int j=0;j<n;j++)native_mmvq(type,w,(char*)q+j*native_q8_1_bytes(ni),ref+j*no,ni,no,1,s);
   native_mmvq(type,w,q,y,ni,no,n,s);ck(cudaStreamSynchronize(s));
   std::vector<float>a(n*no),b(n*no);ck(cudaMemcpy(a.data(),y,a.size()*4,cudaMemcpyDeviceToHost));ck(cudaMemcpy(b.data(),ref,b.size()*4,cudaMemcpyDeviceToHost));
   int mismatches=0;double maxerr=0;for(size_t j=0;j<a.size();j++){if(memcmp(&a[j],&b[j],4))mismatches++;maxerr=std::max(maxerr,std::abs(double(a[j])-b[j]));if(!std::isfinite(a[j]))failed++;}
   double absdiff=0,absref=0;for(size_t j=0;j<a.size();j++){absdiff+=std::abs(double(a[j])-b[j]);absref+=std::abs(double(b[j]));}
   double relative=absdiff/(absref+1e-30);
   if(std::getenv("STRATA_BENCH_ALLOW_ROUNDING")){if(relative>1e-5)failed++;}
   else if(mismatches)failed++;
   for(int i=0;i<10;i++)native_mmvq(type,w,q,y,ni,no,n,s);
   cudaEvent_t start,end;ck(cudaEventCreate(&start));ck(cudaEventCreate(&end));ck(cudaEventRecord(start,s));
   for(int i=0;i<100;i++)native_mmvq(type,w,q,y,ni,no,n,s);
   ck(cudaEventRecord(end,s));ck(cudaEventSynchronize(end));float ms;ck(cudaEventElapsedTime(&ms,start,end));
   printf("tensor=%s type=%d in=%d out=%d cols=%d bytes=%zu us=%.3f bitdiff=%d maxerr=%.9g relative=%.9g\n",t.name.c_str(),type,ni,no,n,bytes,ms*10,mismatches,maxerr,relative);
   ck(cudaEventDestroy(start));ck(cudaEventDestroy(end));tested++;
  }
  ck(cudaFree(w));ck(cudaFree(x));ck(cudaFree(q));ck(cudaFree(y));ck(cudaFree(ref));
 }
 printf("tested=%d failures=%d\n",tested,failed);ck(cudaStreamDestroy(s));return failed||!tested?1:0;
}
