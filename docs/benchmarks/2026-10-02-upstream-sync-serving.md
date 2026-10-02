# Targeted checks after the 0.1.34 rebase

Upstream: `1678de333d0e0711bc414ad992b640e1a37dd814` (2026-10-02).

Tested contribution source: `4f0f97ccdf73e623ea0f2e7fd68fa8571990d0ed`.

These are fresh build and regression checks after replaying the contribution on upstream main.
The larger fleet and context matrices dated 2026-10-01 remain measurements of 0.1.33.
They have not been relabeled as 0.1.34 results. This update does not repeat the full matrix.

The earlier contribution history is retained in tag `archive/pre-sync-20261002-non-mtp-serving`.

## Completed checks

| Host | Check | Result |
|---|---|---|
| llm-49 | `serving-configure` | Pass |
| llm-49 | `serving-build` | Pass |
| llm-49 | `python-server-regression` | Pass |
| llm-49 | `serving-old-new-pcie-identity` | Pass |
| llm-49 | `non-mtp-old-new-identity` | Pass |
| llm-49 | `serving-8k-off-on` | Pass |

Builds use the exact exported commits and verified source/archive hashes, Release mode,
and the same pinned GGML revision and toolchains as the previous reports.
All model checks use GSQ-RCO IQ3_S and Q8 KV, text only; MTP uses window 4/threshold 0.5
for timing and threshold 0 for identity checks. Startup is excluded and the OS file cache
was not reset. Engines run privately through stdio.

The identity comparisons use the previously tested serving binary versus the rebased
serving binary, eight requests per arm, with MTP and without MTP. They check output
tokens, authoritative state, known answers and live-prefix reuse. The MTP check also
alternates request-level PCIe fractions between 0 and 0.55. These are cross-version
regressions, not a fresh upstream-versus-patch comparison.

All 88 Python mock-server tests passed, including the new upstream client-disconnect handling.

## Fresh short-request observations

Up to 512 output tokens; natural EOS. Different context allocations and output lengths
make these unsuitable for a direct comparison with the older long-output matrix.

| Host / run | MTP | Task | Input / allocation | Output | Prefill s | Output tok/s | Total s | Effective tok/s |
|---|---|---|---:|---:|---:|---:|---:|---:|
| llm-49 / serving-8k-off-on | off | coding | 8192 / 9728 | 125 | 1.87 | 59.57 | 3.97 | 31.47 |
| llm-49 / serving-8k-off-on | off | writing | 8192 / 9728 | 233 | 1.77 | 72.91 | 4.97 | 46.89 |
| llm-49 / serving-8k-off-on | on | coding | 8192 / 9728 | 125 | 1.88 | 75.44 | 3.54 | 35.35 |
| llm-49 / serving-8k-off-on | on | writing | 8192 / 9728 | 232 | 1.78 | 98.23 | 4.14 | 56.04 |

[Machine-readable evidence](2026-10-02-upstream-sync-serving.json) includes build commands, source/binary hashes,
test log summaries, request settings and full timed outputs.
