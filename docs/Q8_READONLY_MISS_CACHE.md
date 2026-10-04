# Read-only Q8 miss cache experiment

Target: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X,
128GB RAM. Full Unsloth Q8_0, FP16 KV, native 32K and 128K. Main is unchanged.

This branch adds an opt-in secondary GPU cache for the missed experts that the
existing CPU/GPU split already sends to the GPU. It preserves the primary
adaptive cache and the grouped expert arithmetic. A hit avoids another upload;
discarding a copy performs no writeback. The authoritative expert remains in
the primary GPU/RAM/file hierarchy. This differs from retaining promoted
experts in RAM, whose tested unseeded FIFO policy saved too few writebacks.

`STRATA_Q8_MISS_CACHE_WAYS=0` is the default. Values 1 through 16 allocate that
many slots per layer. Four ways across 48 layers cost 1,002,700,800 bytes
(0.934 GiB), plus small metadata and the original staging area. The experiment
requires uniform Q8_0, whole-model CUDA verification, `--pcie-mode auto` or
`kernel`, and no `--spec-split`. It has not been validated on HIP or other GPUs.

## Copy and lifetime contract

1. The GPU reserves every existing hit before selecting victims. A miss cannot
   overwrite a later member of the same group. Excess misses use staging.
2. A replacement slot becomes invalid before its bytes are overwritten.
3. A parallel copy kernel fills missing weights. A separate publication kernel
   runs after the entire copy kernel; only then does the new expert tag become
   valid. The host never treats an enqueued copy as a completed cache fill.
4. Copies, publication, expert consumers and later eviction use the same stream.
   This initial implementation adds no cross-stream lifetime dependency.
5. Cache tags describe immutable weights, not KV or recurrent state. Accepted
   or rejected drafts may warm the cache, but cannot publish a partial fill.
   The existing fatal verifier-release path continues refusing later windows.
6. No CPU/GPU assignment, expert ordering, grouped launch geometry, model bytes,
   sampling policy or primary expert residency changes.

The component fixture exercises complete byte comparisons at the actual
5,222,400-byte expert size, small boundary sizes, changing groups through captured
graphs, hits with null RAM pointers, eviction, bypass, per-slot guards, immutable
RAM sources, and plans abandoned before fill/publication. It does not by itself
prove full-model cancellation or speculative-state correctness.

## Evidence gates

Implementation is prepared; no performance claim yet. The independent miss
trace is queued ahead of this branch's component gates. Use measured reuse and
native-128K free VRAM to select capacity. Component gates must pass before a
model run. Then compare default-off and cache-on with the same binary, exact
token/work checks for plain and MTP, first-divergence/work reporting for n-gram
and combined, and a request cancellation/checkpoint test. Repeat gains and
test both native contexts before publishing a speed claim.

Per-request logs report cumulative completed groups, hits, uploads, bypasses
and logical bytes saved/uploaded. Difference adjacent reports for a request.
These are payload counts, not PCIe hardware counters. Cache hit rate alone does
not prove a throughput gain; extra launches and memory traffic can outweigh it.

`test_q8_readonly_lifecycle.py` prepares paired plain/MTP gates against the
component-tested binary: a normal 32K request, A/B/A conversation and checkpoint
restoration, STOP after 16 delivered tokens, then another request. It requires
matching main-model state fingerprints and tokens on the normal/checkpoint
requests. If asynchronous STOP performs different work between arms, the
post-cancel state comparison is reported as unequal-work, not claimed exact.
This harness is prepared, not yet passed. Performance runs follow only after
its successful completion. The serving path remains private.
