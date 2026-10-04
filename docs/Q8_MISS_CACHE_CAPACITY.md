# Q8 secondary GPU cache capacity experiment

Configuration branch of [Niko1221/Strata](https://github.com/Niko1221/Strata),
through this fork's ownership, duplex, read-only cache and copy-grid work.
Target: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X,
128GB RAM, full Unsloth Q8_0, FP16 KV and native context. No new inference
kernel or cache replacement policy is introduced by this branch.

## Why test more duplicate GPU storage

The four-way cache avoided 1,945 of 24,188 GPU miss uploads in a prior 32K MTP
coding/editing pair (8.04%). An earlier trace replay projected 25.74% fewer
uploads with 16 ways. That is a trace projection, not a measured model result.
The separate 8GiB seeded-RAM experiment saved 11.30% of eviction writebacks
without improving TPS. This experiment instead removes uploads from the
per-layer miss path when the same expert is used again.

The corrected host-traffic diagnostic found almost unchanged editing RAM read
volume with overlapped uploads, while the exposed copy join fell substantially
and CPU/concurrent intervals grew. Avoiding an upload can reduce contention as
well as its own wait. Whether this improves request time is the question.

## Controlled configuration and invariants

| Secondary ways per layer | Duplicate GPU allocation |
|---:|---:|
| 4 | 0.934 GiB |
| 8 | 1.868 GiB |
| 16 | 3.735 GiB |

Each allocation is `ways * 48 * 5,222,400` bytes, plus small metadata. Canonical
copies remain in RAM. Discarding secondary entries requires no D2H writeback;
the separate primary cache still performs ownership exchanges.

Keep 15,472 primary slots (75.25GiB), the full 44.28GiB RAM complement,
32-block overlapped copies, ownership rotation, duplex, PCIe fraction 0.55 and
all completion dependencies fixed. More secondary capacity consumes extra
VRAM; it must not silently displace primary experts or shrink required buffers.
The startup benchmark guard checks placement and a locked lookup table.
Record reported free VRAM and check actual allocation before extending context.

## Gate and first screen

Extend the byte fixture to full 5,222,400-byte blobs at 8 and 16 ways, in both
serial and captured-overlap paths. It includes cache hits with null RAM source
pointers, eviction, group sizes up to 16, independent output checks, guards,
immutable sources, graph replays and abandoned fills. Run the complete fixture
at 32 blocks, then memcheck/initcheck, before a fresh engine build.

First compare 4/8/16 ways for MTP at 32K input + 1,024 output, then 4/16 for
plain, n-gram and combined modes. Each arm starts a fresh engine and runs coding
then editing. Require exact plain/MTP output and recorded work; preserve any
timing-sensitive n-gram work or token differences. The changed upload/hit counts
are the intended intervention, not an exact-transfer-work comparison.

No component or throughput result is claimed yet. Extend only useful paths to
native 128K, repeat gains with reversed ordering, and add lifecycle coverage
before claiming broader readiness. A miss-rate improvement without better
request time, excessive VRAM pressure, or any unexplained output/state change
falsifies the proposed benefit. Keep the four-way path as an alternative.
