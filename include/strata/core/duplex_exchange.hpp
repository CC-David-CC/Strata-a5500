#pragma once

#include <cuda_runtime.h>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace strata::core {

// One caller, unique GPU slots, and distinct pinned host buffers per batch.
// The caller must finish its prior uses of the slots before enqueue(), then wait
// for the fill stream before reading the new slots or reusing any host buffer.
// Each overwrite waits for its own eviction; other slots' D2H and H2D may overlap.
class DuplexExchange {
public:
    struct Copy { void* slot; const void* incoming; void* outgoing; size_t bytes; };
    DuplexExchange() = default;
    DuplexExchange(const DuplexExchange&) = delete;
    DuplexExchange& operator=(const DuplexExchange&) = delete;
    ~DuplexExchange() { close(); }

    cudaError_t open(size_t capacity) {
        if (evict_ || !capacity) return cudaErrorInvalidValue;
        cudaError_t e = cudaStreamCreateWithFlags(&evict_, cudaStreamNonBlocking);
        if (e != cudaSuccess) return e;
        events_.resize(capacity, nullptr);
        for (auto& event : events_) {
            e = cudaEventCreateWithFlags(&event, cudaEventDisableTiming);
            if (e != cudaSuccess) { close(); return e; }
        }
        return cudaSuccess;
    }

    cudaError_t enqueue(const Copy* copies, size_t count, cudaStream_t fill) {
        if (!evict_ || count > events_.size() || (count && !copies)) return cudaErrorInvalidValue;
        // Reject an invalid list before submitting any work.
        for (size_t i = 0; i < count; ++i)
            if (!copies[i].slot || !copies[i].incoming || !copies[i].outgoing || !copies[i].bytes)
                return cudaErrorInvalidValue;
        if (!count) return cudaSuccess;
        fill_ = fill;
        submitted_ = true;
        for (size_t i = 0; i < count; ++i) {
            const Copy& c = copies[i];
            cudaError_t e = cudaMemcpyAsync(c.outgoing, c.slot, c.bytes, cudaMemcpyDeviceToHost, evict_);
            if (e == cudaSuccess) e = cudaEventRecord(events_[i], evict_);
            if (e == cudaSuccess) e = cudaStreamWaitEvent(fill, events_[i], 0);
            if (e == cudaSuccess) e = cudaMemcpyAsync(c.slot, c.incoming, c.bytes, cudaMemcpyHostToDevice, fill);
            if (e != cudaSuccess) { drain(); return e; }
            ++copies_;
            payload_ += 2 * c.bytes;
        }
        return cudaSuccess;
    }

    cudaError_t wait_evictions() {
        return evict_ ? cudaStreamSynchronize(evict_) : cudaErrorInvalidValue;
    }

    // Also used on submission errors and early teardown. The borrowed fill
    // stream and all buffers must outlive this object (or an explicit close()).
    cudaError_t drain() {
        const cudaError_t a = evict_ ? cudaStreamSynchronize(evict_) : cudaSuccess;
        const cudaError_t b = submitted_ ? cudaStreamSynchronize(fill_) : cudaSuccess;
        submitted_ = false;
        return a != cudaSuccess ? a : b;
    }
    void close() {
        drain();
        for (auto e : events_) if (e) cudaEventDestroy(e);
        events_.clear();
        if (evict_) cudaStreamDestroy(evict_);
        evict_ = nullptr;
        fill_ = nullptr;
    }
    uint64_t copies() const { return copies_; }
    uint64_t payload_bytes() const { return payload_; } // D2H + H2D, not a byte saving

private:
    cudaStream_t evict_ = nullptr, fill_ = nullptr;
    std::vector<cudaEvent_t> events_;
    bool submitted_ = false;
    uint64_t copies_ = 0, payload_ = 0;
};

} // namespace strata::core
