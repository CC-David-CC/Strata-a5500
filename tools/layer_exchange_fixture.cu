#include "strata/core/duplex_exchange.hpp"
#include "strata/core/exchange_storage.hpp"
#include "strata/core/layer_exchange_events.hpp"
#include <cuda_runtime.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <vector>

using strata::core::DuplexExchange;
using strata::core::LayerExchangeEvents;
using strata::core::detail::ExchangeStorage;
#define CU(call) do { const auto e=(call); if(e!=cudaSuccess) { \
    std::fprintf(stderr,"%d: %s: %s\n",__LINE__,#call,cudaGetErrorString(e)); std::exit(2); } } while(0)
#define REQUIRE(x) do { if(!(x)) { std::fprintf(stderr,"%d: %s\n",__LINE__,#x); std::exit(3); } } while(0)

// A bounded test-only delay lets us prove early admission occurs while the
// later layer is still unavailable. The callback never calls a CUDA API.
struct Gate {
    std::mutex mu;
    std::condition_variable cv;
    bool release = false;
    std::atomic<bool> timed_out{false};
    static void CUDART_CB hold(void* p) {
        auto& g=*static_cast<Gate*>(p);
        std::unique_lock<std::mutex> lock(g.mu);
        if(!g.cv.wait_for(lock,std::chrono::seconds(15),[&]{return g.release;})) g.timed_out=true;
    }
    void open() { {std::lock_guard<std::mutex> lock(mu);release=true;} cv.notify_all(); }
};

static uint8_t byte(size_t expert,size_t offset) {
    return (uint8_t)(expert*97+offset*31+(offset>>8));
}

void exercise(size_t bytes,bool delay_later) {
    constexpr size_t copies=6,experts=12,layers=6;
    const size_t stride=bytes+32;
    uint8_t *ram=nullptr,*spare=nullptr,*ram_alias=nullptr,*spare_alias=nullptr,*gpu=nullptr;
    CU(cudaHostAlloc((void**)&ram,copies*bytes,cudaHostAllocMapped));
    CU(cudaHostAlloc((void**)&spare,copies*bytes,cudaHostAllocMapped));
    CU(cudaHostGetDevicePointer((void**)&ram_alias,ram,0));
    CU(cudaHostGetDevicePointer((void**)&spare_alias,spare,0));
    CU(cudaMalloc((void**)&gpu,copies*stride));
    std::vector<uint8_t> reference(experts*bytes),initial(copies*stride,0xcd);
    for(size_t e=0;e<experts;++e) for(size_t b=0;b<bytes;++b) reference[e*bytes+b]=byte(e,b);
    std::memcpy(ram,reference.data(),copies*bytes);
    for(size_t q=0;q<copies;++q) std::memcpy(initial.data()+q*stride,reference.data()+(q+copies)*bytes,bytes);
    CU(cudaMemcpy(gpu,initial.data(),initial.size(),cudaMemcpyHostToDevice));
    std::vector<uint64_t> offsets(experts,~uint64_t{0});
    for(size_t q=0;q<copies;++q) offsets[q]=q*bytes;
    ExchangeStorage storage;
    std::string error;
    REQUIRE(storage.initialize(offsets,ram,ram_alias,copies*bytes,spare,spare_alias,copies,bytes,error));
    cudaStream_t fill;
    CU(cudaStreamCreateWithFlags(&fill,cudaStreamNonBlocking));
    {
        DuplexExchange first,rest;
        CU(first.open(copies)); CU(rest.open(copies));
        LayerExchangeEvents ready;
        CU(ready.open(layers));
        const std::vector<int> schedule{0,0,2,3,3,5};
        REQUIRE(!ready.prepare({}));
        REQUIRE(!ready.prepare({0,6}));
        REQUIRE(!ready.prepare({2,0}));
        REQUIRE(!ready.prepare({-1}));
        for(size_t round=0;round<3;++round) {
            REQUIRE(ready.prepare(schedule));
            REQUIRE(!ready.prepare(schedule));
            REQUIRE(ready.wait(0)==cudaErrorInvalidValue); // never accept an unrecorded event
            REQUIRE(!ready.admit(0) && !ready.finish());
            REQUIRE(!ready.pending(1) && ready.wait(1)==cudaSuccess);
            REQUIRE(ready.wait(layers)==cudaErrorInvalidValue);
            REQUIRE(!ready.completion_event(0) && ready.completion_event(1));
            REQUIRE(!ready.completion_event(copies));
            size_t ins[copies],outs[copies];
            ExchangeStorage::View incoming[copies],outgoing[copies];
            std::vector<DuplexExchange::Copy> batch;
            for(size_t q=0;q<copies;++q) {
                ins[q]=storage.resident(q).host?q:q+copies;
                outs[q]=ins[q]==q?q+copies:q;
                incoming[q]=storage.resident(ins[q]);outgoing[q]=storage.spare(q);
                batch.push_back({gpu+q*stride,incoming[q].host,outgoing[q].host,bytes,ready.completion_event(q)});
            }
            Gate gate;
            if(delay_later) {
                // Separate D2H schedulers avoid reusing their internal events.
                // The fill order and per-layer completion contract are identical.
                CU(first.enqueue(batch.data(),2,fill));
                CU(cudaLaunchHostFunc(fill,&Gate::hold,&gate));
                CU(rest.enqueue(batch.data()+2,copies-2,fill));
            } else CU(first.enqueue(batch.data(),copies,fill));
            REQUIRE(ready.arm() && !ready.arm());
            auto admit=[&](size_t layer) {
                const auto* range=ready.pending(layer);
                if(!range) {CU(ready.wait(layer));return;}
                CU(ready.wait(layer));
                for(size_t q=range->begin;q<range->end;++q) {
                    REQUIRE(!std::memcmp(outgoing[q].host,reference.data()+outs[q]*bytes,bytes));
                    REQUIRE(!std::memcmp(incoming[q].host,reference.data()+ins[q]*bytes,bytes));
                    REQUIRE(storage.commit(ins[q],outs[q],q,outgoing[q].host,bytes));
                    REQUIRE(storage.resident(outs[q]).host==outgoing[q].host);
                    REQUIRE(storage.spare(q).host==incoming[q].host);
                }
                REQUIRE(ready.admit(layer) && !ready.admit(layer));
            };
            admit(1); admit(0); // unaffected layer needs no transfer; first affected layer can proceed
            if(delay_later) {
                REQUIRE(cudaEventQuery(ready.completion_event(copies-1))==cudaErrorNotReady);
                for(size_t q=2;q<copies;++q) {
                    REQUIRE(storage.resident(ins[q]).host==incoming[q].host);
                    REQUIRE(storage.resident(ins[q]).device==incoming[q].device);
                    REQUIRE(storage.spare(q).host==outgoing[q].host);
                    REQUIRE(!std::memcmp(incoming[q].host,reference.data()+ins[q]*bytes,bytes));
                }
                gate.open();
            }
            REQUIRE(!ready.finish());
            // The final round models cancellation before later layers run: the
            // request-boundary drain must still publish every remaining owner.
            for(size_t layer=0;layer<layers;++layer) admit(layer);
            REQUIRE(ready.finish() && !gate.timed_out.load());
            CU(cudaStreamSynchronize(fill));
            std::vector<uint8_t> got(copies*stride);
            CU(cudaMemcpy(got.data(),gpu,got.size(),cudaMemcpyDeviceToHost));
            for(size_t q=0;q<copies;++q) {
                REQUIRE(!std::memcmp(got.data()+q*stride,reference.data()+ins[q]*bytes,bytes));
                for(size_t b=bytes;b<stride;++b) REQUIRE(got[q*stride+b]==0xcd);
                REQUIRE(!std::memcmp(storage.resident(outs[q]).host,reference.data()+outs[q]*bytes,bytes));
            }
        }
        REQUIRE(storage.exchanges()==18 && storage.avoided_bytes()==18*bytes);
        std::printf("PASS layer readiness bytes=%zu delayed=%d: early layer before late fill, "
                    "three ownership cycles, full bytes, guards, boundary drain\n",bytes,(int)delay_later);
    }
    CU(cudaStreamDestroy(fill));
    CU(cudaFree(gpu)); CU(cudaFreeHost(spare)); CU(cudaFreeHost(ram));
}

int main() {
    CU(cudaSetDevice(0));
    for(size_t bytes:{size_t(16),size_t(144),size_t(5222400)})
        for(bool delay:{false,true}) exercise(bytes,delay);
    std::puts("PASS layer exchange fixture");
}
