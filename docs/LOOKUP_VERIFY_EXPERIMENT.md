# Prompt lookup and grouped MoE verification

This branch begins from the measured `70ed905` engine. The first experiment changes
configuration and the benchmark harness only. It does not yet replace kernels or
change the verifier's commit policy.

Four arms use the same 65,536-token prompts, int8 KV, model tensors, placement,
sampling, output cap and six-row verifier allocation:

| Arm | MTP window | Prompt lookup minimum match |
|---|---:|---:|
| Serial | Disabled | Disabled |
| N-gram only | Disabled | 3 tokens |
| MTP only | Up to 4 | Disabled |
| Combined | Up to 4 | 3 tokens |

The existing lookup policy estimates accepted tokens per round cost. In combined
mode it currently requires the first lookup token to agree with MTP. It then
chooses a single candidate chain; it does not blindly concatenate incompatible
drafts. Removing that gate or implementing a proposal tree is a separate causal
intervention, not part of the first four-arm comparison.

The existing native MoE planner groups entries by expert within each layer and
window/group. The `kSplit` IQ formats process up to four entries per shared weight
decode. Q4_K, Q5_K, Q5_1 and Q8_0 use the older per-entry dot loop, so grouping does
not yet imply register-level weight reuse for the Unsloth Q4/Q8 paths. Hardware
caches may still serve repeated loads; that needs counters. Every entry retains its activation, routing
weight and output slot. Routed-output combination keeps each token's expert order.
The path already implements part of the requested batching idea.

Measure proposal time, proposed/evaluated/accepted/committed positions, unique
experts per window, union bytes and measured DRAM bytes per committed token before
changing group width. A wider window may increase expert union size, register
pressure or rejected work. Optimizing proposed tokens/s is not the objective.

CPU lookup may overlap GPU MTP work, but only accepted history may be published.
No background writer may mutate the lookup index while another thread reads it.
A small copied proposal or request-local index snapshot is safer than sharing a
mutable index. The initial runs use the existing synchronous lookup to establish
its actual cost before adding threading.

The measurement set must include both repetitive edit/copy tasks and fresh code
or prose. Throughput tests use isolated GPU runs; no numbers have been measured
for this branch yet. Exact-prefix and rollback checks precede a speed claim.
