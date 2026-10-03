# Experimental Q4 decoding on RTX PRO 6000

## 32% faster n-gram editing; 3.2% faster MTP + n-gram editing

This is an experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its model engine belongs to the upstream project and its contributors.
This branch records our Q4 decoding experiments on an **NVIDIA RTX PRO 6000 Blackwell
Workstation Edition (96 GB VRAM)**, Ryzen 9 7950X and **128 GB RAM**, running Linux.

The two headlines are **separate, paired comparisons**; the gains are not additive.
They use full **Unsloth Qwen3.8-Flash-Next UD-Q4_K_XL**, with all experts retained
and resident on the GPU. This is a historical **Strata 0.1.34-based** research
branch, not a claim of these gains over today's upstream release.

| Experiment / editing workload | Output tok/s, control -> candidate | Change | Effective tok/s, control -> candidate |
| --- | ---: | ---: | ---: |
| N-gram only: verification width 4 -> 8 | 249.59 -> 330.34 | **+32.35%** | 80.70 -> 87.65 |
| MTP + n-gram: size GPU resources for the active width | 313.96 -> 324.15 | **+3.25%** | 85.88 -> 86.63 |

Each comparison used **65,536 actual input tokens**, 73,728 allocated context,
**int8 KV**, a 4,096-token output budget and **1,238 actual output tokens**
(the editing answer stopped naturally). Each arm has two observations in ABBA
order, with a fresh engine for each request and identical output tokens across
the compared arms. Effective throughput includes prompt processing and request
overhead, excluding engine startup. These are selected synthetic editing tests,
not a general quality score or a broad statistical performance claim.

## What changed

- **N-gram width:** let a prompt/history match propose a longer verification
  window. Graph preparation is enabled in both arms and its cost is included in
  prompt/request time. This is a configuration improvement on the same engine.
- **Active-width resources:** opt-in kernels size hyperconnection shared memory
  and BF16 accumulator storage for the active batch instead of the maximum
  allocated width. The second comparison keeps verifier allocation/cap at eight,
  MTP cap at four and minimum draft probability at 0.5. Only
  `STRATA_HC_ACTIVE_T=1` and `STRATA_BF16_ACTIVE_T=1` differ from its control.
- The branch also retains speculative commit-boundary fixes, wider-verifier
  diagnostics and later opt-in experiments. They have separate evidence below;
  enabling every experimental switch together is not a tested recommendation.

Experimental speed projection was **off** in these measurements.

## Evidence and exact revisions

| Result | Engine revision | Report and raw observations |
| --- | --- | --- |
| 32% n-gram editing | [`8591dc7`](https://github.com/CC-David-CC/Strata-a5500/commit/8591dc7634e832ed3f766b1d1e6b78c474eb2863) | [Width comparison](docs/VERIFY_WIDTH_CEILINGS.md), [JSON](docs/benchmarks/q4-verify-widths-20261003.json) |
| 3.2% MTP + n-gram editing | [`49b4c76`](https://github.com/CC-David-CC/Strata-a5500/commit/49b4c765359285d78dfec6107fa83577cb0fd2d6) | [Active-width resources](docs/ACTIVE_WIDTH_RESOURCES.md), [JSON](docs/benchmarks/q4-active-width-resources-20261003.json) |

The reports include individual observations, executable hashes, launch settings,
limits and test coverage. The width benchmark used harness revision
[`70ca7c2`](https://github.com/CC-David-CC/Strata-a5500/commit/70ca7c26d99c2025e7ef9492929822a20e96fc21).
For reproduction, check out the recorded engine revision and use the corresponding
report and JSON settings; the branch tip contains later experiments and is not the
binary used for every historical row.

Arithmetic comparisons, CUDA memcheck and synccheck passed for the active-width
kernels. Committed-state and token comparisons passed at 8K input with output
caps 23, 24, 25 and 51. The 64K performance comparisons passed exact output-token
checks; they did not collect a per-step state digest at 64K.

## Other paths and limits

- [Commit boundaries and rollback](docs/SPECULATIVE_COMMIT_BOUNDARIES.md).
- [Wider verifier allocation](docs/WIDE_VERIFY24.md).
- [Later policy and dense tiling experiments](docs/DENSE_TOKEN_TILES.md): includes
  a separate 337.40 tok/s editing result and paths that regressed.
- Known-answer oracle results around 400-440 tok/s receive the answer in advance.
  They measure verifier capacity, **not usable generation speed**.
- The newest tuning on this branch has not been validated with 128K input.
- Q8 weights, other GPUs, other prompts, and FP16 KV require their own results.

For the supported product and installation instructions, use
[upstream Strata](https://github.com/Niko1221/Strata).
The original [license](LICENSE) and third-party notices remain in this fork.
