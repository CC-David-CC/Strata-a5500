# Q8 PDL and independent graph branches: raw evidence

Measured on llm-60, RTX PRO 6000 Blackwell Workstation 96 GB, Ryzen 9 7950X,
128 GB RAM; CUDA 13.2, native sm_120. The implementation is from Hardin22 /
Francesco Albano's upstream PR #904; original authorship is retained.

- `initial-pr904/`: original two-commit PR904 integration, 5 Q2 correctness
  requests and 7 Q8 component-screen requests. One timing per configuration.
- `focused/`: source 70ed61f, only PDL and graph branches, opt-in defaults;
  5 Q2 correctness requests and 6 Q8 requests, including reversed combined pairs.
- `provenance.json`: source, binary, author and branch identity.
- `sha256.json`: hashes of every evidence file except the manifest itself.
- `verify_results.py`: standalone standard-library integrity and comparison verifier.

Run `python verify_results.py` here. It checks request sizes, token IDs,
recorded work including adaptation/transfer counts, PDL activation, and hashes.
`verified-summary.json` captures its output. This is observed equality for
these requests, not a proof for every intermediate state or workload.

Q8 uses actual 32,768 input plus 1,024 forced output tokens; FP16 KV and MTP T4.
Fresh engine per case, no prompt reuse; final ownership drain included in decode.
Startup is recorded separately. The model's experts and PLE are Q8_0, with
compatibility BF16 small projections and a Q5_K output head.

Focused Q8 off/on: 141.146 -> 143.538 tok/s (+1.69%).
Reverse pair: 141.204 -> 144.663 tok/s (+2.45%). Identical tokens/work.
PDL-only: 140.890 (-0.18%); branches-only: 143.153 (+1.42%), single measurements.
Full-request time reduction for the combined pairs is 0.22% and 0.26%.
The earlier PDL-only +0.54% did not repeat as a standalone gain here.

The plans and run.py record full flags, build commands and local file paths.
Model weights are not included. Replace host-specific paths for reproduction.
