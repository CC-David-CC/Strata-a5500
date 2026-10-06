#include "strata/prefill/dg_tail.hpp"
#include <cstdio>
#include <exception>
using strata::prefill::dg_tail::Context;
extern "C" void* dg_create() { try { return new Context; } catch(const std::exception& e) { std::fprintf(stderr,"%s\n",e.what()); return nullptr; } }
extern "C" void dg_destroy(void* p) { delete static_cast<Context*>(p); }
extern "C" int dg_run(void* p,const void* raw,const float* h,const int32_t* counts,float* d,void* stream) {
 return static_cast<Context*>(p)->run(raw,h,counts,d,stream);
}
