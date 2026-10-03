#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace strata::core::detail {

// Non-owning views: the complement and exchange allocations retain their original
// owners until FileExpertSource::close(). A view moves; its bytes and CUDA alias do
// not. This first path requires uniform, fully mapped/pinned expert slots.
class ExchangeStorage {
public:
    struct View {
        uint8_t* host = nullptr;
        const uint8_t* device = nullptr;
    };

    bool initialize(const std::vector<uint64_t>& offsets, uint8_t* resident_host,
                    const uint8_t* resident_device, uint64_t resident_bytes,
                    uint8_t* exchange_host, const uint8_t* exchange_device,
                    size_t count, size_t blob_bytes, std::string& error) {
        error.clear();
        if (active()) { error = "exchange storage already initialized"; return false; }
        if (!resident_host || !resident_device || !exchange_host || !exchange_device ||
            !blob_bytes || !count || !resident_bytes || resident_bytes % blob_bytes ||
            count > std::numeric_limits<size_t>::max() / blob_bytes) {
            error = "invalid uniform mapped exchange geometry"; return false;
        }
        std::vector<View> experts(offsets.size()), spares(count);
        std::vector<bool> used((size_t)(resident_bytes / blob_bytes), false);
        for (size_t i = 0; i < offsets.size(); ++i) {
            const uint64_t at = offsets[i];
            if (at == ~uint64_t{0}) continue;
            if (at >= resident_bytes || at % blob_bytes || used[(size_t)(at / blob_bytes)]) {
                error = "invalid or duplicate resident slot"; return false;
            }
            used[(size_t)(at / blob_bytes)] = true;
            experts[i] = {resident_host + (size_t)at, resident_device + (size_t)at};
        }
        for (bool present : used) if (!present) {
            error = "unassigned resident slot"; return false;
        }
        for (size_t q = 0; q < count; ++q)
            spares[q] = {exchange_host + q * blob_bytes, exchange_device + q * blob_bytes};
        experts_.swap(experts);
        spares_.swap(spares);
        blob_bytes_ = blob_bytes;
        return true;
    }

    bool active() const { return blob_bytes_ != 0; }
    View resident(size_t expert) const {
        return expert < experts_.size() ? experts_[expert] : View{};
    }
    View spare(size_t q) const { return q < spares_.size() ? spares_[q] : View{}; }

    // Only after every CPU reader and H2D copy of `in` has completed, and `out`
    // has landed in spare(q). No allocation, memcpy, or CUDA operation here.
    bool commit(size_t in, size_t out, size_t q, const uint8_t* staged, size_t bytes) {
        if (in >= experts_.size() || out >= experts_.size() || q >= spares_.size() ||
            !experts_[in].host || experts_[out].host || !staged ||
            spares_[q].host != staged || bytes != blob_bytes_) return false;
        experts_[out] = spares_[q];
        spares_[q] = experts_[in];
        experts_[in] = {};
        ++exchanges_;
        avoided_bytes_ += bytes;
        return true;
    }

    uint64_t exchanges() const { return exchanges_; }
    uint64_t avoided_bytes() const { return avoided_bytes_; } // memcpy payload, not read+write total
    void clear() { experts_.clear(); spares_.clear(); blob_bytes_ = 0; exchanges_ = avoided_bytes_ = 0; }

private:
    std::vector<View> experts_, spares_;
    size_t blob_bytes_ = 0;
    uint64_t exchanges_ = 0, avoided_bytes_ = 0;
};

} // namespace strata::core::detail
