# Experimental active-layer expert cache

Experimental native optimization, developed and integration-tested alongside
[the public branch-checkpoint change (#1667)](https://github.com/Niko1221/Strata/pull/1667),
then extracted onto main without its server changes. Inspired by the
[expert-transfer reuse discussion (#1670)](https://github.com/Niko1221/Strata/issues/1670);
independently implemented using the existing per-chunk prefill path.

Set `STRATA_PREFILL_LAYER_CACHE=1` in the engine environment to try it. Default
behavior stays on the ordinary prefill path. This cache complements saved
conversation checkpoints: checkpoints avoid recomputing a known prefix, while
this experiment aims to reduce repeated weight transfers for fresh tokens.

The scheduler walks a bounded window layer by layer. It keeps the normal chunk
size and the existing attention, recurrent, routing and expert kernels. Residual
rows pass through pinned host memory between layers. At each layer, it copies
nonresident expert blobs into a temporary VRAM allocation up to its budget;
remaining experts use the normal streaming path. The initial admission policy
is deterministic expert-ID order, not a learned hot-expert policy. It may load
experts that routing does not use. Existing decode-cache slots are not modified.

| Environment setting | Default | Meaning |
| --- | ---: | --- |
| `STRATA_PREFILL_LAYER_CACHE` | 0 | Enable the experimental scheduler |
| `STRATA_PREFILL_LAYER_CACHE_TOKENS` | 8192 | Window target, rounded to whole chunks, at least two chunks |
| `STRATA_PREFILL_LAYER_CACHE_MIB` | 1536 | Maximum temporary expert VRAM; zero declines the experiment |
| `STRATA_PREFILL_LAYER_CACHE_MARGIN_MIB` | 256 | Free VRAM to leave after allocation; minimum 64 MiB |

The actual weight allocation is bounded by available free VRAM and the largest
layer. Two additional pinned allocations hold the window residuals and 32 expert
staging buffers. Failed allocations fall back before modifying session state.
Read/transfer failures or cancellation after processing starts fail the request;
they do not silently restart on partially advanced state.

Single-GPU native-MMQ text prefill only. Layer splits, peer GPUs, helper stages,
image rows, fused layouts, unsupported expert formats and one-chunk requests
decline the experiment. CPU expert sharing is disabled inside this experimental
schedule; comparisons must account for that setting.

`on_chunk` still supplies each final residual chunk to MTP and progress reporting.
Earlier layers may already be at the window end, so intermediate callbacks must
not save a native checkpoint. `checkpoint_ready(done)` permits saving only when
all layers have reached the same window boundary. PLE token history is restored
to the window's initial history before each layer pass; only layer 1 advances
its convolution state. QSA and GDN visit their token chunks in chronological order.

This prototype does not combine expert rows across chunks and adds no new GPU
kernels. Traffic reduction does not by itself establish a speedup. Validation
must compare against existing automatic chunk sizing, check multi-token output,
and exercise checkpoint reuse/branching/restart before enabling it for service.

`tools/bench_prefill_layer_cache.py --config CONFIG --output NEW_DIRECTORY`
compares off/on with automatic chunk sizing, three repetitions at 4K/8K and
64 generated tokens. A 512-token warmup also generates 64 tokens, so MTP graph
memory is allocated before measurements. It records exact token IDs and fails on output mismatch,
prefix reuse, or a scheduler that never activates. `--reference-exe` can select
an unmodified engine for the off arm. Use `--chunk 512` to compare fixed chunks.
`--cancel-test` additionally cancels an active prompt and checks recovery on the
same engine.

## P4 validation

On one Tesla P4 with Qwen3.8-Flash-Next-GSQ-RCO IQ3_XXS, automatic chunk
sizing and 4,096 fresh prompt tokens, median prompt throughput increased from
108.133524 to 115.816006 tok/s (+7.105%; two repetitions per arm). An initial
8,192-token pair measured 115.079293 to 122.610686 tok/s (+6.545%). All compared
64-token outputs matched exactly. CUDA was built and exercised; HIP and SYCL
builds remain outstanding. These are small samples on one workload.

See [measurements and validation](measurements/p4-layer-cache/README.md) for
per-run data, warmup differences, checkpoint checks and reproduction settings.
