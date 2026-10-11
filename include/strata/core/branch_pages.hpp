#pragma once
#include "strata/core/vmm.hpp"
#include <memory>
#include <vector>

namespace strata::core {

struct BranchPageTable;
using BranchPageSnapshot = std::shared_ptr<const BranchPageTable>;
struct BranchPageInfo {
    uint64_t allocation_id = 0;
    VmmChunk driver_handle = 0;
    uint64_t owners = 0; // owning page tables, excluding temporary instrumentation references
    uint64_t bytes = 0;
};
struct BranchPageCounters {
    uint64_t allocations=0,releases=0,live_bytes=0,cow_pages=0,copied_bytes=0,mappings=0,unmappings=0;
    uint64_t address_reservations=0,address_releases=0;
};

// Derived GPU materialization only: never a replacement for authoritative input
// history or controller state. Each live instance has a single host-thread owner.
// Independent instances may share snapshots. Caller synchronizes all device work
// before freeze/restore/prepare_write/release. Frozen pages become read-only in
// this mapping. Every future kernel write must first pass prepare_write.
class BranchPages {
public:
    BranchPages();
    ~BranchPages();
    BranchPages(const BranchPages&) = delete;
    BranchPages& operator=(const BranchPages&) = delete;
    bool reserve(uint64_t capacity_bytes);
    bool grow(uint64_t mapped_bytes);
    bool clear(); // remove this lease's pages, preserving its virtual address
    BranchPageSnapshot freeze();
    bool restore(const BranchPageSnapshot& snapshot);
    bool prepare_write(uint64_t offset,uint64_t bytes);
    bool release();
    uint8_t* data() const { return mapping_.base(); }
    std::vector<BranchPageInfo> ownership() const;
    static BranchPageCounters counters();
private:
    bool private_table();
    std::shared_ptr<BranchPageTable> table_;
    VmmMapping mapping_; // destroyed before table_ releases physical handles
};

} // namespace strata::core
