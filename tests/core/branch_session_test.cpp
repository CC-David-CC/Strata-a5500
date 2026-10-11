#include "strata/core/branch_session.hpp"
#include "strata/core/conversation_snapshot.hpp"
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <vector>

using namespace strata::core;
static int checks = 0;
static void check(bool ok, const char* what) {
    ++checks;
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", what); std::exit(1); }
}
static void gpu(cudaError_t e) { check(e == cudaSuccess, cudaGetErrorString(e)); }
static std::vector<unsigned char> read(const void* p, size_t n) {
    std::vector<unsigned char> b(n);
    gpu(cudaMemcpy(b.data(), p, n, cudaMemcpyDeviceToHost));
    return b;
}

// Actual CUDA allocations and Strata state layouts. This unit test deliberately
// writes recognizable bytes; it is not a model forward or a G3 acceptance result.
static void exercise(int format) {
    ModelGeometry g;
    g.n_layers = 4;
    g.ssm_state_size = 2; g.ssm_v_heads = 2; g.ssm_conv_channels = 8;
    qsa_set_kv_int8(format == 1);
    qsa_set_kv_q4(format == 2);
    qsa_set_kv_hybrid(format == 3);
    qsa_set_kv_elastic(false, 0);
    qsa_set_kv_resident(0);
    SessionState ss;
    QsaState q;
    ss.max_cells = 8192; ss.layer_hi = 4;
    ss.gdn_alloc = 3; ss.qsa_alloc = 1; ss.qsa_states = &q;
    void* arena = nullptr;
    gpu(cudaMalloc(&arena, qsa_state_bytes(g, ss.max_cells)));
    check(qsa_state_init(g, ss.max_cells, arena, q) != 0, "initialize real QSA layout");
    qsa_state_zero(q, g, nullptr);
    ConversationStateSizes sizes;
    std::string error;
    check(conversation_state_sizes(g, sizes, error), "running-state sizes");
    gpu(cudaMalloc(&ss.gdn_state, sizes.gdn));
    gpu(cudaMalloc(&ss.ple_hist, sizes.ple));
    gpu(cudaMemset(ss.gdn_state, 13, sizes.gdn));
    gpu(cudaMemset(ss.ple_hist, 17, sizes.ple));
    gpu(cudaDeviceSynchronize());
    void* original = q.k_pool ? (void*) q.k_pool : q.k_q ? (void*) q.k_q : (void*) q.k_q4;
    const auto baseline = BranchPages::counters();
    {
        BranchSession session(ss, g, "fixture-contract");
        check(session.bind(error), "bind native page ownership to session");
        const auto address = session.pools().front().address;
        check(address != original, "pointers rebound before graph capture");
        check(session.begin(0, 4097, error), "begin forced prefix");
        check(!session.freeze(error), "pending tokens cannot be frozen");
        check(!session.begin(0, 1, error), "no overlapping write transaction");
        for (const auto& p : session.pools()) gpu(cudaMemset(p.address, 21, p.bytes));
        // The indexer's moving spare row is part of its actual contract.
        gpu(cudaMemset(q.idx_dead, 21, sizes.dead));
        gpu(cudaMemset(q.idx_tail, 25, sizes.tail));
        gpu(cudaMemset(q.idx_block_pos, 0, sizeof(int32_t)));
        std::vector<int32_t> ids(4097, 42);
        check(session.finish(ids, {1.25f, -0.5f}, error), "finish consumed prefix");
        auto root = session.freeze(error);
        check(bool(root), "freeze full state");
        const auto root_pages = session.ownership();
        const auto root_bytes = read(address, session.pools().front().bytes);
        const auto recurrent = read(ss.gdn_state, sizes.gdn);
        const auto ple = read(ss.ple_hist, sizes.ple);
        const auto before = BranchPages::counters();
        check(!session.begin(4096, 1, error), "reject wrong absolute position");
        check(session.begin(4097, 1, error), "make partial tail writable");
        for (const auto& p : session.pools()) {
            const size_t at = p.pooled ? (4097 / 4) * p.bytes_per_cell : 4097 * p.bytes_per_cell;
            gpu(cudaMemset((unsigned char*) p.address + at, 77, p.bytes_per_cell));
        }
        gpu(cudaMemset(ss.gdn_state, 91, sizes.gdn));
        gpu(cudaMemset(ss.ple_hist, 92, sizes.ple));
        check(session.finish({43}, {2.5f, -3.0f}, error), "finish A");
        auto a = session.freeze(error);
        check(bool(a), "freeze A");
        const auto after = BranchPages::counters();
        check(after.copied_bytes - before.copied_bytes <= session.pools().size() * 2 * vmm_granularity(),
              "COW copy bound independent of prefix length");
        check(session.restore(root, error), "restore complete root");
        check(session.pools().front().address == address, "stable address for captured kernels");
        check(read(address, root_bytes.size()) == root_bytes, "root KV byte audit");
        check(read(ss.gdn_state, sizes.gdn) == recurrent, "recurrent state restored");
        check(read(ss.ple_hist, sizes.ple) == ple, "PLE convolution state restored");
        check(session.logits() == std::vector<float>({1.25f, -0.5f}), "root frontier restored");
        check(ss.ple_prev[0] == 42 && ss.ple_prev[1] == 42, "PLE token window restored");
        const auto restored = session.ownership();
        check(restored.size() == root_pages.size(), "same page extent after restore");
        for (size_t i = 0; i < restored.size(); ++i)
            check(restored[i].allocation_id == root_pages[i].allocation_id, "restored identical physical handles");
        check(session.begin(4097, 1, error), "begin B from root");
        gpu(cudaMemset(ss.gdn_state, 93, sizes.gdn));
        check(session.finish({44}, {9.0f, 8.0f}, error), "finish B");
        check(session.restore(a, error), "restore A after B");
        check(session.logits() == std::vector<float>({2.5f, -3.0f}), "A frontier isolated");
        check(session.ids().back() == 43 && session.ids().size() == 4098, "A consumed frontier isolated");
        check(read(ss.gdn_state, sizes.gdn) == std::vector<unsigned char>(sizes.gdn, 91), "A recurrence isolated");
        check(!session.begin(ss.max_cells, 1, error), "capacity overflow refused");
        const auto reset_before = BranchPages::counters();
        check(session.reset(error), "reset private lease without discarding snapshots");
        check(session.ids().empty() && session.logits().empty(), "reset has no consumed frontier");
        check(!session.freeze(error), "empty reset cannot publish logits");
        check(session.pools().front().address == address, "reset keeps captured kernel addresses");
        check(read(address, root_bytes.size()) == std::vector<unsigned char>(root_bytes.size(), 0), "fresh KV is zero");
        check(read(ss.gdn_state, sizes.gdn) == std::vector<unsigned char>(sizes.gdn, 0), "fresh recurrence is zero");
        check(ss.ple_prev[0] == -1 && ss.ple_prev[1] == -1, "reset clears PLE token window");
        check(BranchPages::counters().copied_bytes == reset_before.copied_bytes, "reset does not copy a discarded prefix");
        check(session.begin(0, 1, error), "new independent history after reset");
        check(session.finish({99}, {5.0f, 6.0f}, error), "consume new history");
        check(session.restore(root, error), "restore retained root after reset");
        check(read(address, root_bytes.size()) == root_bytes, "reset did not mutate retained root pages");
        check(session.restore(a, error), "restore retained A after reset");
        check(read(ss.gdn_state, sizes.gdn) == std::vector<unsigned char>(sizes.gdn, 91), "reset did not mutate retained recurrence");
    }
    check((q.k_pool ? (void*) q.k_pool : q.k_q ? (void*) q.k_q : (void*) q.k_q4) == original,
          "release restores borrowed session pointers");
    const auto end = BranchPages::counters();
    check(end.live_bytes == baseline.live_bytes, "all derived GPU pages released");
    gpu(cudaFreeHost(q.host_step)); gpu(cudaFreeHost(q.host_pos));
    gpu(cudaFree(ss.gdn_state)); gpu(cudaFree(ss.ple_hist)); gpu(cudaFree(arena));
}

int main() {
    gpu(cudaSetDevice(0));
    for (int format = 0; format < 4; ++format) exercise(format);
    std::printf("{\"status\":\"PASS\",\"checks\":%d,\"formats\":4,\"model_forward\":false}\n", checks);
}
