#pragma once

#include <cuda_runtime.h>
#include <cstddef>
#include <vector>

namespace strata::core {

// Every slot is unique within a batch. Incoming/outgoing host buffers are
// pinned, distinct and live through completion. The caller waits for H2D before
// changing ownership or issuing the next batch. Each overwrite waits for that
// slot's eviction, while opposite-direction copies of other slots can overlap.
class DuplexExchange {
public:
    struct Copy {
        void* slot; const void* incoming; void* outgoing; size_t bytes;
        cudaEvent_t filled = nullptr; // optional completion after this H2D, never before it
    };
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
        // Validate the whole list before submitting any transfer.
        for (size_t i = 0; i < count; ++i)
            if (!copies[i].slot || !copies[i].incoming || !copies[i].outgoing || !copies[i].bytes)
                return cudaErrorInvalidValue;
        for (size_t i = 0; i < count; ++i) {
            const Copy& c = copies[i];
            cudaError_t e = cudaMemcpyAsync(c.outgoing, c.slot, c.bytes, cudaMemcpyDeviceToHost, evict_);
            if (e != cudaSuccess) return e;
            e = cudaEventRecord(events_[i], evict_);
            if (e != cudaSuccess) return e;
            e = cudaStreamWaitEvent(fill, events_[i], 0);
            if (e != cudaSuccess) return e;
            e = cudaMemcpyAsync(c.slot, c.incoming, c.bytes, cudaMemcpyHostToDevice, fill);
            if (e != cudaSuccess) return e;
            if (c.filled) {
                e = cudaEventRecord(c.filled, fill);
                if (e != cudaSuccess) return e;
            }
        }
        return cudaSuccess;
    }

    cudaError_t wait_evictions() {
        return evict_ ? cudaStreamSynchronize(evict_) : cudaErrorInvalidResourceHandle;
    }

    void close() {
        // H2D is owned and completed by the caller; this object owns only D2H.
        if (evict_) cudaStreamSynchronize(evict_);
        for (auto e : events_) if (e) cudaEventDestroy(e);
        events_.clear();
        if (evict_) cudaStreamDestroy(evict_);
        evict_ = nullptr;
    }

private:
    cudaStream_t evict_ = nullptr;
    std::vector<cudaEvent_t> events_;
};

} // namespace strata::core
