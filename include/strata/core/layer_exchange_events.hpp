#pragma once

#include <cuda_runtime.h>
#include <cstddef>
#include <vector>

namespace strata::core {

// One event after the final fill of each affected layer. The caller owns the
// transfer stream and must drain it before this object or its source buffers
// die. Preparing/arming/waiting/admitting is serialized by the host driver.
class LayerExchangeEvents {
public:
    struct Range { size_t begin = 0, end = 0; bool ready = false, admitted = false; };
    LayerExchangeEvents() = default;
    LayerExchangeEvents(const LayerExchangeEvents&) = delete;
    LayerExchangeEvents& operator=(const LayerExchangeEvents&) = delete;
    ~LayerExchangeEvents() { for (auto event : events_) if (event) cudaEventDestroy(event); }

    cudaError_t open(size_t layers) {
        if (!events_.empty() || !layers) return cudaErrorInvalidValue;
        events_.resize(layers, nullptr);
        ranges_.resize(layers);
        for (auto& event : events_) {
            const auto e = cudaEventCreateWithFlags(&event, cudaEventDisableTiming);
            if (e != cudaSuccess) return e;
        }
        return cudaSuccess;
    }

    bool prepare(const std::vector<int>& layers) {
        if (prepared_ || layers.empty() || events_.empty()) return false;
        // Check the full schedule before changing state. Selection is done by
        // the existing ranker; only its already-selected copy order is sorted.
        for (size_t q = 0; q < layers.size(); ++q)
            if (layers[q] < 0 || (size_t)layers[q] >= events_.size() ||
                (q && layers[q] < layers[q - 1])) return false;
        for (auto& range : ranges_) range = {};
        layers_ = layers;
        for (size_t q = 0; q < layers.size(); ++q) {
            auto& range = ranges_[(size_t)layers[q]];
            if (!q || layers[q] != layers[q - 1]) range.begin = q;
            range.end = q + 1;
        }
        prepared_ = true;
        armed_ = false;
        return true;
    }

    cudaEvent_t completion_event(size_t q) const {
        if (!prepared_ || q >= layers_.size()) return nullptr;
        return q + 1 == ranges_[(size_t)layers_[q]].end ? events_[(size_t)layers_[q]] : nullptr;
    }
    bool arm() {
        if (!prepared_ || armed_) return false;
        armed_ = true; // every completion event has now actually been queued
        return true;
    }
    const Range* pending(size_t layer) const {
        if (!prepared_ || layer >= ranges_.size()) return nullptr;
        const auto& range = ranges_[layer];
        return range.begin != range.end && !range.admitted ? &range : nullptr;
    }
    cudaError_t wait(size_t layer) {
        if (layer >= ranges_.size()) return cudaErrorInvalidValue;
        if (!pending(layer)) return cudaSuccess;
        if (!armed_) return cudaErrorInvalidValue; // unrecorded events are not proof of completion
        const auto e = cudaEventSynchronize(events_[layer]);
        if (e == cudaSuccess) ranges_[layer].ready = true;
        return e;
    }
    bool admit(size_t layer) {
        if (!pending(layer) || !ranges_[layer].ready) return false;
        ranges_[layer].admitted = true;
        return true;
    }
    bool finish() {
        if (!prepared_) return true;
        if (!armed_) return false;
        for (size_t layer = 0; layer < ranges_.size(); ++layer)
            if (pending(layer)) return false;
        prepared_ = armed_ = false;
        layers_.clear();
        return true;
    }

private:
    std::vector<cudaEvent_t> events_;
    std::vector<Range> ranges_;
    std::vector<int> layers_;
    bool prepared_ = false, armed_ = false;
};

} // namespace strata::core
