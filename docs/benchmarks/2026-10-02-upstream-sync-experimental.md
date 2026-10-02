# Targeted checks after the 0.1.34 rebase

Upstream: `1678de333d0e0711bc414ad992b640e1a37dd814` (2026-10-02).

Tested contribution source: `549bdbca2317b739b0edbe38a530929307251988`.

These are fresh build and regression checks after replaying the contribution on upstream main.
The larger fleet and context matrices dated 2026-10-01 remain measurements of 0.1.33.
They have not been relabeled as 0.1.34 results. This update does not repeat the full matrix.

The earlier contribution history is retained in tag `archive/pre-sync-20261002-fleet-mmvq`.

## Completed checks

| Host | Check | Result |
|---|---|---|
| llm-60 | `experimental-configure` | Pass |
| llm-60 | `experimental-build` | Pass |
| llm-60 | `gr-parity` | Pass |
| llm-60 | `mmvq-default-parity` | Pass |
| llm-60 | `experimental-8k-default` | Pass |
| llm-60 | `experimental-8k-max4` | Pass |

Builds use the exact exported commits and verified source/archive hashes, Release mode,
and the same pinned GGML revision and toolchains as the previous reports.
All model checks use GSQ-RCO IQ3_S and Q8 KV, text only; MTP uses window 4/threshold 0.5
for timing and threshold 0 for identity checks. Startup is excluded and the OS file cache
was not reset. Engines run privately through stdio.

GR max4 is checked against the default with all supported window/control combinations.
The MMVQ check includes the native output head and every supported real tensor shape.
The 8K default/max4 code and prose outputs have identical token IDs.
The timing pair below is a smoke check, not a repeated speedup experiment.
Both experimental options remain disabled by default. The RX 5500 XT one-warp path
was not retimed in this targeted rebase check; its prior measured result remains dated.

## Fresh short-request observations

Up to 512 output tokens; natural EOS. Different context allocations and output lengths
make these unsuitable for a direct comparison with the older long-output matrix.

| Host / run | MTP | Task | Input / allocation | Output | Prefill s | Output tok/s | Total s | Effective tok/s |
|---|---|---|---:|---:|---:|---:|---:|---:|
| llm-60 / experimental-8k-default | on | coding | 8192 / 9728 | 125 | 1.46 | 245.72 | 1.97 | 63.44 |
| llm-60 / experimental-8k-default | on | writing | 8192 / 9728 | 232 | 1.32 | 164.28 | 2.74 | 84.74 |
| llm-60 / experimental-8k-max4 | on | coding | 8192 / 9728 | 125 | 1.44 | 253.19 | 1.94 | 64.50 |
| llm-60 / experimental-8k-max4 | on | writing | 8192 / 9728 | 232 | 1.33 | 168.94 | 2.70 | 85.83 |

[Machine-readable evidence](2026-10-02-upstream-sync-experimental.json) includes build commands, source/binary hashes,
test log summaries, request settings and full timed outputs.
