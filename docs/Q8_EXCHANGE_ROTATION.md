# Q8 expert exchange buffer experiment

Branch: `perf/q8-exchange-buffer-rotation`.
Target: llm-60, NVIDIA RTX PRO 6000 Blackwell Workstation Edition **96 GB**,
Ryzen 9 7950X, 128 GB installed RAM. Full Unsloth Q8_0, FP16 KV.

**Status: implementation prepared; validation and throughput results pending.**
There is no measured model speedup for this change yet.

## The change

The resident RAM mode keeps the experts absent from the GPU cache. Promoting
expert A frees its RAM slot; evicting expert B first copies B from VRAM into a
temporary host buffer. The original commit copies B again into A's former RAM
slot. This experiment adopts B's temporary buffer as its resident storage and
recycles A's former RAM slot as the next eviction buffer.

Enable with `STRATA_EXCHANGE_ROTATE=1`. Unset or `0` retains the original copy
path. The RAM and exchange allocations keep their original lifetime owners;
only descriptors containing host and CUDA device addresses move. The model
weights, resident expert count, cache replacement policy and quantization stay
the same. The GPU-to-host eviction transfer is still required.

This first implementation accepts **equal-size expert blocks with the entire
resident complement pinned and mapped**. Partial pinning, pageable memory and
mixed block sizes explicitly fall back to the copy path. The maximum exchange
capacity must be reserved before rotation is initialized; later growth is
rejected because the original exchange allocation may contain live experts.
Existing serve/generate callers reserve their maximum once before inference.

## Correctness contract

- The D2H eviction finishes before the evicted expert is published for readers.
- Existing CPU completion and H2D completion waits precede ownership commit.
- Every resident expert and spare has exclusive ownership of one buffer.
- CUDA aliases move with host pointers. No alias is reconstructed from a stale
  offset into the original RAM allocation.
- Staged overrides, file fallback, `blob`, `copy_blob`, prefetch, pin checks and
  device address lookups resolve the same committed storage.
- No transfer wait, residency publication order, stream lifetime or kernel
  arithmetic changes. Invalid commit metadata fails closed.

The counter `host memcpy bytes avoided` counts payload bytes. Avoiding an N-byte
copy removes an N-byte CPU read and N-byte CPU write at the software level; it
does not itself establish measured DRAM traffic or an end-to-end speedup.

## Validation and measurement

`exchange_storage_test` exercises 12,304 ownership transitions, odd sizes,
unaligned host addresses, actual Q8-sized blocks, distinct device aliases,
repeated reuse, invalid commits, guards and exact bytes. Run under ASan/UBSan.

`file_expert_source_test --rotation-gpu` exercises the real source API and CUDA
transfers with copy, rotation, and pageable fallback: staged reads, promotion,
eviction, host copies, CUDA alias reads, disk fallback, growth rejection,
close/reopen and byte equality. Run under Compute Sanitizer memcheck.

`tools/run_q8_exchange_rotation_fleet.py` joins the private fleet GPU queue:

1. Component tests, source API tests and GPU memory checks.
2. Old binary versus new binary with rotation disabled, 8K input/256 output.
3. Rotation off/on for serial, MTP, n-gram and combined modes, **64K input +
   1,024 output**, 73,728 allocation, FP16 KV, fresh coding/editing requests.
4. Fixed 16,400 GPU slots for serial/n-gram and 16,192 for MTP/combined; automatic
   CPU/PCIe split, 96 adaptive swaps, completion waits enabled, ESP disabled.
5. Exact token IDs, first divergence, resource telemetry, copy counters and
   unprofiled decode speed. Reverse-order repeat for any exact-output candidate
   with a first-run task improvement of at least 3%.

A semantic mismatch remains a failed gate for that path, even if throughput
increases. The storage fixtures and model comparison answer different questions;
both are required before accepting the change. Public serving is unaffected.
