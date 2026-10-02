# experimental-kernels measurements

**Validation completed on 2026-10-02 UTC. Retained failures and partial success are identified below.**

Base: Strata 0.1.33 (`aeb35be`). GSQ-RCO IQ3_S, Q8 KV, text only.
Generation rates exclude prefill. Effective rates include prefill; startup is excluded.
Each row shows actual output length. Long prompts allow 4096 output tokens.
MTP throughput uses a four-token window and threshold 0.5. Prompt reuse is off;
the OS file cache is not reset. Requests run sequentially on each host.

The r730 row represents one Tesla P4, GPU 2 / NUMA node 1 / 13 workers.
The a5500 host has a consumer Radeon RX 5500 XT 8GB. llm-79 has 40 GB
installed system RAM and a 24 GB Radeon RX 7900 XTX.

RX 5500 XT rows use combined tree `d37c41f`; other focused rows use `99ec975`.
Stock RTX PRO controls use untouched upstream `aeb35be`. See the report
for the exact tree-recreation recipe and repeated-pair interpretation.

| Host / trial | MTP | Task | Input / output | Prefill s | First token s | Generation tok/s | Total s | Effective tok/s |
|---|---|---|---:|---:|---:|---:|---:|---:|
| llm-49 / focused-default-8k | on | counting | 8192 / 512 | 1.86 | 1.89 | 135.11 | 5.65 | 90.57 |
| llm-49 / focused-grmax4-8k | on | counting | 8192 / 512 | 1.86 | 1.89 | 135.51 | 5.64 | 90.73 |
| llm-60 / focused-default-64k | on | coding | 65536 / 2213 | 9.56 | 9.58 | 223.42 | 19.47 | 113.67 |
| llm-60 / focused-default-64k | on | writing | 65536 / 1756 | 9.52 | 9.53 | 160.36 | 20.48 | 85.76 |
| llm-60 / focused-grmax4-64k | on | coding | 65536 / 2213 | 9.61 | 9.64 | 228.15 | 19.32 | 114.55 |
| llm-60 / focused-grmax4-64k | on | writing | 65536 / 1756 | 9.56 | 9.58 | 164.07 | 20.27 | 86.61 |
| llm-60 / stock-64k-a | on | coding | 65536 / 2213 | 9.55 | 9.58 | 224.54 | 19.42 | 113.98 |
| llm-60 / stock-64k-a | on | writing | 65536 / 1756 | 9.43 | 9.45 | 160.88 | 20.35 | 86.28 |
| llm-60 / stock-64k-b | on | coding | 65536 / 2213 | 9.60 | 9.63 | 222.19 | 19.57 | 113.07 |
| llm-60 / stock-64k-b | on | writing | 65536 / 1756 | 9.62 | 9.64 | 159.54 | 20.64 | 85.08 |
| llm-60 / pair-1-default | on | coding | 65536 / 2213 | 9.53 | 9.56 | 224.60 | 19.39 | 114.11 |
| llm-60 / pair-1-default | on | writing | 65536 / 1756 | 9.45 | 9.46 | 160.93 | 20.36 | 86.23 |
| llm-60 / pair-1-max4 | on | coding | 65536 / 2213 | 9.58 | 9.61 | 228.57 | 19.27 | 114.84 |
| llm-60 / pair-1-max4 | on | writing | 65536 / 1756 | 9.55 | 9.56 | 164.38 | 20.24 | 86.77 |
| llm-60 / pair-2-default | on | coding | 65536 / 2213 | 9.62 | 9.65 | 222.73 | 19.57 | 113.10 |
| llm-60 / pair-2-default | on | writing | 65536 / 1756 | 9.57 | 9.58 | 159.81 | 20.56 | 85.39 |
| llm-60 / pair-2-max4 | on | coding | 65536 / 2213 | 9.61 | 9.64 | 228.28 | 19.31 | 114.58 |
| llm-60 / pair-2-max4 | on | writing | 65536 / 1756 | 9.54 | 9.55 | 164.16 | 20.24 | 86.76 |
| llm-60 / pair-3-default | on | coding | 65536 / 2213 | 9.61 | 9.64 | 222.82 | 19.55 | 113.18 |
| llm-60 / pair-3-default | on | writing | 65536 / 1756 | 9.52 | 9.54 | 159.67 | 20.53 | 85.54 |
| llm-60 / pair-3-max4 | on | coding | 65536 / 2213 | 9.63 | 9.66 | 227.67 | 19.36 | 114.29 |
| llm-60 / pair-3-max4 | on | writing | 65536 / 1756 | 9.62 | 9.63 | 163.81 | 20.34 | 86.32 |
| llm-79 / focused-default-8k | on | counting | 8192 / 512 | 25.03 | 25.29 | 19.36 | 51.49 | 9.94 |
| llm-79 / focused-grmax4-8k | on | counting | 8192 / 512 | 43.45 | 43.71 | 17.91 | 72.04 | 7.11 |
| g3070 / focused-default-8k | on | counting | 8192 / 512 | 19.97 | 20.03 | 44.37 | 31.51 | 16.25 |
| g3070 / focused-grmax4-8k | on | counting | 8192 / 512 | 19.97 | 20.03 | 44.35 | 31.52 | 16.24 |
| r730 / focused-default-8k | on | counting | 8192 / 512 | 93.37 | 93.46 | 23.64 | 115.03 | 4.45 |
| r730 / focused-grmax4-8k | on | counting | 8192 / 512 | 93.42 | 93.51 | 24.05 | 114.71 | 4.46 |
| a5500 / focused-8k-a | on | coding | 8192 / 2688 | 101.54 | 101.66 | 16.17 | 267.79 | 10.04 |
| a5500 / focused-8k-a | on | writing | 8192 / 1453 | 99.04 | 99.14 | 13.06 | 210.28 | 6.91 |
| a5500 / focused-8k-b | on | coding | 8192 / 2688 | 107.17 | 107.29 | 16.32 | 271.92 | 9.89 |
| a5500 / focused-8k-b | on | writing | 8192 / 1453 | 100.61 | 100.71 | 13.09 | 211.64 | 6.87 |
| a5500 / focused-8k-candidate | on | coding | 8192 / 2673 | 102.79 | 102.91 | 16.95 | 260.51 | 10.26 |
| a5500 / focused-8k-candidate | on | writing | 8192 / 1601 | 100.16 | 100.26 | 13.52 | 218.57 | 7.32 |

## Reproduction and interpretation

Use `tools/bench_mtp_modes.py` with the recorded configuration and source
commit. The JSON includes allocated context, resolved engine settings,
prompt/output hashes, binary/harness hashes, toolchain arguments and gates.
Output hashes identify matching text; the original token arrays and logs
are retained with the local fleet evidence. Different MTP modes can produce
different answers and lengths. These measurements are not quality scores.

[Measurements and configurations](2026-10-01-experimental-kernels.json).
