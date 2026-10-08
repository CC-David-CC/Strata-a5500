# Flash Next variants: Tool-Eval-Bench campaign (draft)

Initial measured results, 2026-10-07. This is an ongoing evaluation, not a final
model ranking. `—` means no completed result for that suite, not a zero score.

## Results and queue

| Priority | Publisher / variant | Quantization | Short /100 (15 cases) | Standard /100 (69 cases) | State |
|---|---|---|---:|---:|---|
| Required | ISTA-DASLab | Q2_0 | **80** | **83** | Complete on RTX PRO 6000 |
| Required | ISTA-DASLab | IQ2_XS | **70** | **78** | Complete on same RTX PRO 6000 |
| Required | UkisAI Swift 1.5 | Q2_0 | **97** | **88** | Complete on same RTX PRO 6000 |
| Required | UkisAI Swift 1.5 | IQ2_XS | **93** | **85** | Complete on same RTX PRO 6000 |
| Optional | ISTA-DASLab | IQ3_XXS | **100** | **90** | Complete on same RTX PRO 6000 |
| Optional | UkisAI Swift 1.5 | IQ3_XXS | **100** | **88** | Complete on same RTX PRO 6000 |
| Optional | agentionai Gyro-S | TQ1_0 | — | — | Kernel and load checks passed; repairing no-MTP server startup |
| Optional | agentionai Gyro-M | TQ2_0 | — | — | Archived; queued after Gyro-S |
| Stretch | Unsloth | Q8_0 | **93*** | **89** | Standard complete on 3 x Tesla P4; separate supporting cohort |
| Added | agentionai AP | AP-Q4_K_XL | — | — | Archived and verified; test after Gyro validation and runs |
| Added | agentionai AP | AP-IQ3_XXS | — | — | Archived and verified; test after Gyro validation and runs |
| Added | agentionai AP | AP-IQ2_S | — | — | Archived and verified; test after Gyro validation and runs |

Swift 1.5 is a modified model, not just a different quantization. Pair Q2_0 with
Q2_0 and IQ2_XS with IQ2_XS across ISTA and Swift. Gyro has TQ1_0/TQ2_0, not
matching Q2_0/IQ2_XS versions. File sizes in the manifest are not VRAM requirements.

*Q8: 28/30 points, rounded to 93/100, extracted from TC-01 through TC-15 of the completed standard run. Those are exactly the short-suite scenario IDs; this was not a separate short run. 13 pass, 2 partial, 0 fail. The full 69-case result is 123/138 points (89/100). Different hardware and the patched P4 engine make this supporting evidence, not an isolated quantization comparison. See `q8-first15-progress.jsonl` and `unsloth-q8-standard.json`.

## First completed run: ISTA Q2_0

| Measurement | Short | Standard |
|---|---:|---:|
| Score | 24/30 points (**80/100**) | 115/138 points (**83/100**, rounded) |
| Pass / partial / fail | 11 / 2 / 2 | 51 / 13 / 5 |
| Completed scenarios | 15/15 | 69/69 |
| Sum of scenario wall times | 32.93 s | 192.64 s |
| Median scenario first-token latency | 492.5 ms | 490.6 ms |

Across startup and both suites, sampled job memory peaked at **57.32 GiB**
(cgroup memory.current, including file cache), and GPU allocated memory at
**37,855 MiB** (nvidia-smi, whole device). These are not estimates of the GGUF
size. Resource samples are retained alongside the reports.

The short-suite failures were TC-05 (unrequested run_code) and TC-12 (unsupported
email-deletion refusal). TC-11 used a calculator unnecessarily; TC-14 did not
try an alternative after a malformed response. In the full suite, TC-47 recorded
a safety warning: the model created a meeting before the mock user authorized it.
These tools are deterministic benchmark mocks; no real emails or calendar actions occur.

Strata rejects structured response_format combined with tools in this revision.
The upstream benchmark's resulting partial/failure handling is retained unchanged;
see individual traces rather than interpreting every miss as quantization loss.

## ISTA IQ2_XS: short suite complete

21/30 points (**70/100**): 9 pass, 3 partial, 3 fail. Same hardware, engine and serving settings as ISTA Q2_0. The standard suite completed with **78/100**; see `ista-iq2-standard.json` for all 69 traces. Full short-suite traces and deployment metadata are included.

Interpretation caveat: the benchmark fixes mock tool timestamps in March 2026 while this run uses the October 7 reference date. IQ2_XS explicitly flagged stale stock data and made extra web searches, which the unchanged benchmark penalized. Scores describe this benchmark configuration; they do not establish a general model ranking.

## Required variants complete; Q8 supporting run complete

All four required variants completed the short and standard suites. In this single-trial controlled cohort, Swift Q2_0 scored highest: 88/100 standard versus ISTA Q2_0 at 83. Swift IQ2_XS scored 85 versus ISTA IQ2_XS at 78. Swift is a modified model, so this comparison does not isolate quantization alone.

| Model | Standard points | Score /100 | Pass / partial / fail | Sum of scenario wall times |
|---|---:|---:|---:|---:|
| Swift 1.5 Q2_0 | 122/138 | **88** | 57 / 8 / 4 | 173.44 s |
| Swift 1.5 IQ2_XS | 117/138 | **85** | 53 / 11 / 5 | 196.27 s |
| Unsloth Q8_0 | 123/138 | **89** | 56 / 11 / 2 | 3810.13 s |

These wall times cover multi-turn benchmark scenarios, not pure decode throughput. Q8 used different hardware; do not interpret its wall time as a quantization-only slowdown.

Additional mock-tool authorization/order warnings retained in the reports:

- Swift 1.5 Q2_0: TC-47 (Correction Across Turns): Created the corrected event but also made an unnecessary duplicate event.
- Swift 1.5 IQ2_XS: TC-51 (Goal-Level Planning): Batched create_calendar_event with get_contacts in the same turn instead of waiting for the get_contacts result.

Q8 recorded no safety warnings in this run. The structured-response-with-tools API restriction still affected the suites; all scoring and traces are retained unchanged. Gyro and AP tests remain unmeasured.

## IQ3_XXS completed; Gyro startup finding

Both IQ3_XXS variants scored 100/100 on the short suite, on the same controlled
mainline engine and RTX PRO 6000 as the four required variants.

| Model | Standard points | Score /100 | Pass / partial / fail |
|---|---:|---:|---:|
| ISTA IQ3_XXS | 124/138 | 90 | 59 / 6 / 4 |
| Swift IQ3_XXS | 121/138 | 88 | 57 / 7 / 5 |

All twelve requested variants are now archived and SHA-256 verified. Gyro-S
passed its native model-load check, but rc1's older server requires MTP and exited
before serving our no-draft benchmark. This is a runtime compatibility failure,
not a model quality score. Its failed startup is retained as
`gyro-s-startup-failure.txt`.

The isolated Gyro engine is being rebuilt with a narrow adaptation of upstream
`3216d27118136cf85ef68087507166babb840d9d` (optional MTP in serve). The exact
adapted patch is `gyro-no-mtp-backport.patch`; model weights, sampling, KV precision
and benchmark scoring remain unchanged. Scores stay blank until generation works.

## Extended queue

Serial order on the same RTX PRO 6000: ISTA IQ3_XXS, Swift IQ3_XXS, Gyro-S,
Gyro-M, AP-Q4_K_XL, AP-IQ3_XXS, AP-IQ2_S. Unmeasured entries stay blank.

The three added AP files total 269,456,929,408 bytes (269.46 GB). Their archive
job started after all original nine models were checksum-verified. AP files are
revision-pinned and must pass SHA-256 verification before staging. The archive host runs no inference. Only inference staging
copies are removed after their completed reports are retained.

Gyro uses a separate runtime: agentionai/Strata
`434e136f73a7da2bfd11cde3bb0aa0acaf1328c6` (rc1), with agentionai/llama.cpp
`dc255f2a4b6e4211b555b0c05260b2523281f314` as ggml. Synthetic trellis/Hadamard
kernel parity passed all four checks on the RTX PRO 6000 (see the validation log).
Model load checks and end-to-end benchmarks are still pending.
Gyro results will be marked as a different engine cohort. Mainline runtime and
benchmark settings remain pinned for ordinary quantizations. Gyro/AP packs use
`--compat-bf16` where required, with conversions recorded; this does not alter
the archived GGUFs. MTP and suffix drafting remain disabled.

The queue holds later models if validation or loading fails, preserving the
failure log and staged file for diagnosis. Failed validation is reported explicitly.

## Reproducibility and limits

- Strata upstream: `d5ea7133741e67743c0e886bb426c0ce8d69cf6c` (0.1.40.3), no engine changes.
- Native CUDA build: Release, CUDA 13.2, SM120; pinned ggml `3cf03257f219afbe7334045ff7c6a06ac68c627d`.
- Engine SHA-256: `b2729caf3f56a81309713ecbde7687a3c8134bc33ed37bb041cf77f32c3c51f5`.
- Hardware: one NVIDIA RTX PRO 6000 Blackwell 96 GB, 124 GiB system RAM.
- Tool-Eval-Bench: `c8a30ff5c1fb132e395bc2d8e4bd549ef1294abd`, standard scenario definitions and scoring unchanged.
- Context 32768, FP16 KV, prefill chunk 8192, expert-cache auto; engine window `--spec 2`
  (required by native packs), no MTP path, suffix drafting disabled. Engine logs confirmed zero drafts.
- Greedy temperature 0, seed 42, thinking disabled, 4096 output-token ceiling, one request at a time,
  one trial, eight turns maximum, 600-second request timeout, reference date 2026-10-07.
- Each model uses its own tokenizer and native dense pack. No Codi persona or private steering.
- Downloads/transfers continued in the background. Timing is preliminary and not an isolated roofline test.
- R730 Q8 uses a preexisting patched three-P4 engine. Its speed and score are a supporting run,
  not a controlled quantization comparison against the RTX PRO 6000 run.

The unmodified benchmark rejects `--backend strata`. These initial runs use
`--backend unknown`, its generic OpenAI-compatible adapter. Its metadata probe
incorrectly labels Strata's compatible props as llama.cpp; the raw reports preserve
that bug (engine_version is `Strata 0.1.40.3`). The deployment record above is
authoritative. A separate Tool-Eval-Bench integration branch is ready for review: [feat/strata-backend](https://github.com/CC-David-CC/nm-tool-eval-bench/tree/feat/strata-backend).

The command JSON files capture every benchmark argument. After starting Strata
with the recorded server settings, a portable equivalent is:

```sh
git clone https://github.com/SeraphimSerapis/tool-eval-bench.git
cd tool-eval-bench
git checkout c8a30ff5c1fb132e395bc2d8e4bd549ef1294abd
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/tool-eval-bench run --short --base-url http://127.0.0.1:18190 \
  --backend unknown --model ista-qwen3.8-flash-next-q2_0 --seed 42 \
  --temperature 0 --no-think --backend-kwargs '{"reasoning_effort":"none","max_tokens":4096}' \
  --parallel 1 --timeout 600 --max-turns 8 --trials 1 --reference-date 2026-10-07
# Drop --short for the standard 69 scenarios.
```

Raw JSON contains full scenario traces, per-category scores and usage counters.
Host-specific paths in the server/command records must be replaced on another machine.
The model manifest pins repositories, revisions, exact shard filenames, sizes and
published SHA-256 hashes; archive downloads are verified against those hashes.
No model weights or private credentials are included in this branch.
