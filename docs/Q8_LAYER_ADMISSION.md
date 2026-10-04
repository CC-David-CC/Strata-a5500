# Q8 adaptive expert admission by layer

Branch `perf/q8-layer-admission`, derived from the measured copy-grid branch
and [Niko1221/Strata](https://github.com/Niko1221/Strata). Initial hardware is
llm-60: RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X, 128GB RAM.
Full Unsloth Q8_0, FP16 KV and native RoPE stay fixed.

## Evidence and hypothesis

The original adaptive transfer list is ranked by gain across all layers. The
next verification window waits for the complete list before doing useful work.
In the earlier 32K coding/editing MTP trace, **96 of 144 exchange batches did
not touch layer 0**. Layers 0–7 needed **14.18% of the copies**, but their last
required copy appeared after **84.56% of aggregate copy-list positions** in
the original order. These are observed schedule positions, not timing or a
speed projection. That trace used 15,472 primary slots and no secondary cache.

Sorting alone cannot remove the existing whole-batch wait. This experiment
sorts only the already-selected pairs by layer and uses completion events to
admit each layer independently. The hypothesis is that early dense/expert
work can hide some later adaptive D2H/H2D work. Extra event calls, publication
work or memory contention could erase the gain. A lower wait bucket without
better committed-token throughput is a negative result.

## State and invariants

1. Rank, select and apply the original batch-capacity cut first. Stable sorting
   changes copy order, not which `(incoming, outgoing, GPU slot)` pairs move.
2. Each slot overwrite still waits for its own eviction's D2H completion.
3. Record a layer event after its final incoming H2D. A never-recorded event
   is rejected as a readiness proof; a prepared batch must be armed explicitly.
4. Before that layer's CPU pool builds the expert plan, wait for its event,
   stage outgoing RAM ownership, commit buffer rotation and publish incoming
   GPU residency. Other layers' RAM inputs and exchange destinations stay live.
5. The host planner publishes flag A only after that admission. Device-side
   residency planning is rejected because it could consume a stale table.
6. After verification, retire the batch and upload the coherent full device
   table. No next adaptive batch reuses its spare buffers before retirement.
7. STOP, EOS, output limits and request/checkpoint boundaries drain the final
   batch. The drain remains inside measured decode time. Error unwinding drains
   transfer streams before their buffers/events are destroyed.

Weights, arithmetic, CPU/GPU miss fraction, primary/secondary capacity and
speculation policy stay fixed. The implementation does not remove the GPU's
data-dependency waits. `STRATA_EXCHANGE_LAYER_ADMISSION=1` implies deferred
publication; its absence or `0` retains the parent schedule. The separately
tested whole-batch deferred option remains available for causal comparison.

The first scope rejects device planning, split verification, peer/remote GPU
consumers and router lookahead. The current host-planned, one-GPU benchmark
does not use those paths. Any mixed/file/unpinned exchange is rejected rather
than silently proceeding without a readiness event. CUDA is the test target;
no HIP result is claimed.

## Prepared validation and measurements

- Component fixture: real D2H/H2D transfers, complete bytes, destination guards,
  three ownership cycles at 16, 144 and 5,222,400-byte expert sizes, unchanged
  RAM inputs for pending layers, and a bounded test-only delay proving early
  admission occurs before later layers are ready. Request-boundary draining
  is checked. Invalid schedules and unarmed/premature admission are rejected.
- Compute Sanitizer memcheck/initcheck on that fixture; original duplex
  fixture checks the optional completion field's default behavior.
- ASan/UBSan and TSan on ownership, including other still-pending transfers'
  address/alias/byte stability after a partial commit.
- Build the frozen branch with ccache, then actual-model plain/MTP lifecycle
  comparisons: normal request, STOP, next request, MTP checkpoint switching
  and restoration, token streams and main-model state digests. Require full
  45,342MiB RAM arena, fixed primary slots, FP16 KV and a locked lookup table
  before sending any prompt. Do not time a clamped placement.
- Same-binary native 32K input + 1,024 output in plain, MTP, n-gram and combined
  modes. Hold 15,472 primary slots, four secondary slots/layer, 32 copy blocks,
  overlap, PCIe fraction 0.55 and ownership/duplex fixed. Compare against the
  parent binary as well; include a whole-batch deferred MTP control.
- Exact plain/MTP tokens and recorded work are required. Retain n-gram's
  timing-dependent work/output differences. Record actual admitted layers,
  logical D2H/H2D payload, wait/ownership/worker timing and effective throughput.
- Repeat useful gains and extend to native 128K before a performance claim.

Status: component/sanitizer/build gates and all 33 lifecycle requests passed. All nine 32K configurations (18 throughput requests) completed. Reverse-order 32K MTP completed with positive exact gains; native 128K is running.
The raw schedule analysis is included in
[the supporting trace analysis](benchmarks/q8-layer-readiness-projection-20261004.json).


## First gate run and harness correction

The frozen `523a8809` engine passed ownership ASan/UBSan and TSan, the real
CUDA per-layer transfer fixture, Compute Sanitizer memcheck/initcheck, the
original duplex fixture, worker sanitizers and the ccache build/relink check.
Its engine SHA256 was
`95290a8a30c5d8d8984b02b5b7fc3128c8d2745f139891e5bdb9a5a9b5e6a7b9`.

The following lifecycle attempt failed before starting any model or request:
Python evaluated `dict.get`'s legacy default eagerly, causing `KeyError('ways')`
even with an explicit variant list. The corrected helper selects explicit
variants first, retains the legacy plan, and rejects empty or malformed lists.
Local checks exercised both actual explicit plans, legacy fallback, and
empty/null/object rejection. This correction changes no engine code. A fresh
frozen run retained all lifecycle and model gates. The results below were collected after that correction.

[Passed gates and rejected harness attempt](benchmarks/q8-layer-components-harness-repair-20261004.json).


## First same-binary MTP result (provisional)

Native **32,768 input + 1,024 output**, FP16 KV, 40,960 allocated context.
Same `ac398f5e` source and SHA256
`95290a8a30c5d8d8984b02b5b7fc3128c8d2745f139891e5bdb9a5a9b5e6a7b9`
in all three configurations; all fixed placement/startup checks passed.

| Schedule | Coding output tok/s | Editing output tok/s | Coding effective tok/s | Editing effective tok/s |
|---|---:|---:|---:|---:|
| Parent whole-batch wait | 135.007 | 119.003 | 66.002 | 62.551 |
| Whole-batch deferred publication | 136.355 | 119.565 | 66.342 | 62.646 |
| Per-layer admission | **144.557** | **124.430** | **68.267** | **64.016** |

Per-layer admission improved generation by **7.07% / 4.56%** (coding/editing)
and effective output throughput by **3.43% / 2.34%**. Tokens, measured work,
secondary-cache counters and primary D2H/H2D bytes matched exactly. Each
configuration moved 19.71456GB for coding and 21.6938496GB for editing in each
primary transfer direction. The improvement came from scheduling, with the
same payload. Worker join/admission intervals overlap GPU work and must not
be summed as separate time savings.

All six lifecycle arms passed: plain/MTP times parent, deferred and per-layer
schedules, **33 requests**, including STOP/following requests and MTP checkpoint
switching/restoration. Those checks are not throughput measurements.

**This is a first pair, without a confidence interval or 128K result.** Remaining
plain/n-gram/combined cases and reverse-order repetitions are still needed.
N-gram's timing-dependent policy will be qualified separately.

[Raw lifecycle, build and first MTP evidence](benchmarks/q8-layer-first-mtp-20261004.json).


## Complete first 32K matrix

Nine configurations completed, including the deferred MTP comparator above. All
requests used 32,768 input + 1,024 output and the same fixed configuration.

| Mode / task | Control output tok/s | Per-layer output tok/s | Output gain | Control effective tok/s | Per-layer effective tok/s | Qualification |
|---|---:|---:|---:|---:|---:|---|
| plain / coding | 75.195 | 77.516 | +3.09% | 47.666 | 48.537 | Exact tokens and measured work |
| plain / editing | 63.784 | 65.536 | +2.75% | 43.062 | 43.851 | Exact tokens and measured work |
| mtp / coding | 135.007 | 144.557 | +7.07% | 66.002 | 68.267 | Exact tokens and measured work |
| mtp / editing | 119.003 | 124.430 | +4.56% | 62.551 | 64.016 | Exact tokens and measured work |
| ngram / coding | 80.431 | 78.870 | -1.94% | 49.674 | 49.059 | First token difference 120, different work |
| ngram / editing | 115.595 | 108.651 | -6.01% | 61.761 | 59.715 | Matching tokens, different work |
| mtp-ngram / coding | 136.944 | 143.822 | +5.02% | 66.510 | 68.169 | First token difference 311, different work |
| mtp-ngram / editing | 120.726 | 122.801 | +1.72% | 63.040 | 63.564 | Matching tokens, different work |

Plain and MTP also matched primary exchange bytes and secondary cache counters.
The n-gram-only path lost 1.94% coding and 6.01% editing, with different chosen
windows/work; the earlier schedule remains a useful configuration for that
path. Combined MTP+n-gram gained 5.02%/1.72%, also with different work. Those
comparisons are not isolated identical-work scheduling gains. No single
configuration is declared best for every mode.

[Complete first 32K evidence](benchmarks/q8-layer-complete-32k-20261004.json).
The reversed-order MTP pair below and native 128K pairs in all four modes use
the same already-built binary. Reverse MTP completed; 128K is still running.


## Reversed-order 32K MTP repeat

Candidate ran first, then a fresh same-binary control. These numbers use that
fresh control, not the older forward-order control. Same 32,768 input + 1,024
output, 40,960 allocation and configuration as the first matrix.

| Task | Fresh control tok/s | Per-layer tok/s | Gain | Control effective tok/s | Per-layer effective tok/s |
|---|---:|---:|---:|---:|---:|
| coding | 136.422 | 144.427 | +5.87% | 66.372 | 67.831 |
| editing | 119.304 | 124.356 | +4.23% | 62.637 | 64.008 |

Both requests matched tokens, measured work, primary transfer/swap counts and
secondary-cache counters. The gain survived both run orders; two pairs are
not a confidence interval or a broader-workload guarantee.

[Raw reverse pair](benchmarks/q8-layer-reverse-32k-20261004.json). Native 128K
pairs in all four modes are running on the same unchanged binary.
