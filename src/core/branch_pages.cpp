#include "strata/core/branch_pages.hpp"
#include <cuda_runtime.h>
#include <atomic>
#include <exception>
#include <limits>
#include <new>

namespace strata::core {
namespace {
struct Counters {
    std::atomic<uint64_t> next_id{1},allocations{0},releases{0},live_bytes{0},cow_pages{0},copied_bytes{0};
};
Counters& counts() { static auto* c=new Counters; return *c; }
struct PhysicalPage {
    VmmChunk handle=0;
    uint64_t id=0,bytes=0;
    PhysicalPage() {
        handle=vmm_chunk_new();
        if (!handle) throw std::bad_alloc();
        bytes=vmm_granularity();
        auto& c=counts();
        id=c.next_id.fetch_add(1);
        ++c.allocations;
        c.live_bytes+=bytes;
    }
    ~PhysicalPage() {
        if (!vmm_chunk_release(handle)) std::terminate();
        auto& c=counts();
        ++c.releases;
        c.live_bytes-=bytes;
    }
};
}

struct BranchPageTable {
    uint64_t capacity=0;
    std::vector<std::shared_ptr<PhysicalPage>> pages;
};

BranchPages::BranchPages() = default;
BranchPages::~BranchPages() { if (!release()) std::terminate(); }
bool BranchPages::release() {
    if (!mapping_.release()) return false;
    table_.reset();
    return true;
}
bool BranchPages::reserve(uint64_t bytes) {
    const auto g=vmm_granularity();
    if (!g || !bytes || bytes>std::numeric_limits<uint64_t>::max()-g+1 || !release()) return false;
    try {
        auto table=std::make_shared<BranchPageTable>();
        table->capacity=((bytes+g-1)/g)*g;
        if (!mapping_.reserve(table->capacity)) return false;
        table_=std::move(table);
        return true;
    } catch (...) { return false; }
}
bool BranchPages::private_table() {
    if (!table_) return false;
    if (!table_.unique()) {
        try { table_=std::make_shared<BranchPageTable>(*table_); }
        catch (...) { return false; }
    }
    return true;
}
bool BranchPages::grow(uint64_t bytes) {
    if (!table_ || bytes>table_->capacity || !private_table()) return false;
    const auto g=vmm_granularity();
    const auto n=(bytes+g-1)/g;
    try {
        table_->pages.reserve(n);
        while (table_->pages.size()<n) {
            auto page=std::make_shared<PhysicalPage>();
            const auto i=table_->pages.size();
            if (!mapping_.map(i,page->handle,true)) return false;
            // Retain ownership even when zeroing fails; discard this private lease.
            table_->pages.push_back(std::move(page));
            if (cudaMemset(data()+i*g,0,g)!=cudaSuccess || cudaDeviceSynchronize()!=cudaSuccess) return false;
        }
        return true;
    } catch (...) { return false; }
}
BranchPageSnapshot BranchPages::freeze() {
    if (!table_) return {};
    for (size_t i=0;i<table_->pages.size();++i) if (!mapping_.protect(i,false)) return {};
    return table_;
}
bool BranchPages::restore(const BranchPageSnapshot& snapshot) {
    if (!snapshot) return false;
    // Keep it alive even when restoring a snapshot of this range itself.
    std::shared_ptr<BranchPageTable> table;
    try { table=std::make_shared<BranchPageTable>(*snapshot); }
    catch (...) { return false; }
    if (mapping_.capacity()==table->capacity && mapping_.base()) {
        if (!mapping_.clear()) return false;
        table_.reset();
    } else if (!release() || !mapping_.reserve(table->capacity)) return false;
    table_=std::move(table);
    for (size_t i=0;i<table_->pages.size();++i)
        if (!mapping_.map(i,table_->pages[i]->handle,false)) { release(); return false; }
    return true;
}
bool BranchPages::prepare_write(uint64_t offset,uint64_t bytes) {
    if (!table_) return false;
    const auto g=vmm_granularity();
    const auto extent=table_->pages.size()*g;
    if (offset>extent || bytes>extent-offset || !private_table()) return false;
    if (!bytes) return true;
    const auto last=(offset+bytes-1)/g;
    try {
        for (auto i=offset/g;i<=last;++i) {
            if (table_->pages[i].use_count()==1) {
                if (!mapping_.protect(i,true)) return false;
                continue;
            }
            auto replacement=std::make_shared<PhysicalPage>();
            VmmMapping temporary;
            if (!temporary.reserve(g) || !temporary.map(0,replacement->handle,true)) return false;
            if (cudaMemcpy(temporary.base(),data()+i*g,g,cudaMemcpyDeviceToDevice)!=cudaSuccess ||
                cudaDeviceSynchronize()!=cudaSuccess) return false;
            ++counts().cow_pages;
            counts().copied_bytes+=g;
            if (!temporary.release()) std::terminate();
            if (!mapping_.unmap(i)) return false;
            if (!mapping_.map(i,replacement->handle,true)) { release(); return false; }
            table_->pages[i]=std::move(replacement);
        }
        return true;
    } catch (...) { return false; }
}
std::vector<BranchPageInfo> BranchPages::ownership() const {
    std::vector<BranchPageInfo> out;
    if (table_) for (const auto& page:table_->pages)
        out.push_back({page->id,page->handle,(uint64_t)page.use_count(),page->bytes});
    return out;
}
BranchPageCounters BranchPages::counters() {
    const auto& c=counts();
    const auto m=vmm_mapping_counters();
    return {c.allocations.load(),c.releases.load(),c.live_bytes.load(),c.cow_pages.load(),c.copied_bytes.load(),
        m.mappings,m.unmappings,m.reservations,m.address_releases};
}
} // namespace strata::core
