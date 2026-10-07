# Flash Next variants: Tool-Eval-Bench campaign (draft)

Initial measured results, 2026-10-07. This is an ongoing evaluation, not a final
model ranking. `—` means no completed result for that suite, not a zero score.

## Results and queue

| Priority | Publisher / variant | Quantization | Short /100 (15 cases) | Standard /100 (69 cases) | State |
|---|---|---|---:|---:|---|
| Required | ISTA-DASLab | Q2_0 | **80** | **83** | Complete on RTX PRO 6000 |
| Required | ISTA-DASLab | IQ2_XS | — | — | Verified archive; LAN staging, then RTX PRO 6000 |
| Required | UkisAI Swift 1.5 | Q2_0 | — | — | Downloading; queued for same RTX PRO 6000 |
| Required | UkisAI Swift 1.5 | IQ2_XS | — | — | Downloading/queued; same RTX PRO 6000 |
| Optional | ISTA-DASLab | IQ3_XXS | — | — | Verified archive; evaluation planned |
| Optional | UkisAI Swift 1.5 | IQ3_XXS | — | — | Download queued; evaluation planned |
| Optional | agentionai Gyro-S | TQ1_0 | — | — | Download queued; compatibility untested |
| Optional | agentionai Gyro-M | TQ2_0 | — | — | Download queued; compatibility untested |
| Stretch | Unsloth | Q8_0 | — | — | Standard suite running on 3 x Tesla P4; separate supporting cohort |

Swift 1.5 is a modified model, not just a different quantization. Pair Q2_0 with
Q2_0 and IQ2_XS with IQ2_XS across ISTA and Swift. Gyro has TQ1_0/TQ2_0, not
matching Q2_0/IQ2_XS versions. File sizes in the manifest are not VRAM requirements.

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
authoritative. A separate Tool-Eval-Bench integration PR is in preparation.

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
