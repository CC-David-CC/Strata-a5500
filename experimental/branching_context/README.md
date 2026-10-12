# Immutable branching contexts — draft

Continue two different futures from the same consumed prefix while keeping the
prefix and every saved future immutable. Rewind a branch reference without
deleting history, and rebuild from that history when numerical checkpoints have
been evicted.

This is a local Python API and an experimental native CUDA backend. Its public
boundary is a consumed token: selecting or streaming a token alone does not
commit a snapshot. The mathematical contract is in
[spec/branching-context-api.md](spec/branching-context-api.md).

The draft is ready for review after initial validation. Full G0–G5 certification
is incomplete. See [the measured results](evidence/draft-validation.json).

## Implementation

- `src/context_time_travel/store.py` owns the single canonical parent-linked
  history and controller records. Named branches are separate revisioned
  references with CAS and retry receipts.
- `real.py` materializes optional checkpoints behind leases and publishes
  consumed-token frontiers. RNG draw state, grammar, penalties, stopping and
  decoding state belong to the canonical controller, rather than being assumed
  to exist in a native state export.
- `strata_backend.py` adapts the private `strata-branch` pipe. CUDA VMM pages
  share retained allocations and copy writable tails. Recurrent state and
  frontiers have explicit ownership; activation can still copy those buffers.
- `strata-fresh` starts an empty process/session for each full token history.
  The recorded oracle binary was built separately at revision `857ace6c`; it
  accepts no branch checkpoint or retained handle.
- Native page hashes, ownership, allocation/release, forward-work and copy
  counters are read directly. Image handles are removed from a live-entry list
  when released, and page integrity is checked before activation.

Positions and RoPE/YaRN settings stay bound to the model contract. Sharing a
prefix does not permit moving its keys to a different logical position or
changing its positional semantics.

The native patch is based on checkpoint revision `282f2495`. The draft PR uses
`review/immutable-branching-base` as its base so its diff excludes the earlier
Responses/server work. The Python API in this directory has no HTTP service,
database server or GUI dependency and adds no serving route.

## Executed validation

The tested native revision is `d702b68d`, using Qwen3.8-Flash-Next Q8_0 weights,
FP16 KV and the pinned `Verifier.run(T=1)` operator on Linux/CUDA.

| Check | Observed result |
| --- | --- |
| G0 logical/reference suite | 51 passed; no failures or skips |
| Model-free demo and mutation smoke | Demo passed; four mutants rejected |
| Current-build G3-004 | One unchanged registered method passed |
| Forced A/B futures | Eight fresh full-vocabulary comparisons; maximum absolute logit error 0.0 |
| Immutable retained state | Seven images; 28 physical-byte audits passed |
| Hot append work | Six appends; one new forward token each; zero prefix recomputation |
| Actual ownership | Each initial child shared 24 physical allocations with the root |
| Resource scope | 216 COW pages / 452984832 copied bytes; sampled VMM peak 704643072 bytes |
| Release | Eight image/handle owners released; tracked payload/handle bytes returned to zero; native process closed |

The short case consumed 24 SUT tokens and 84 independent-oracle tokens. The
initial run took 88.0105 seconds; the published-source rerun passed the same
case in 70.1252 seconds. These are shared-host observations, not throughput benchmarks.
VMM counters exclude model arenas and temporary workspaces. Final native
counters precede native teardown; process closure is checked separately.

Earlier evidence on native `2622c3a5` passed all 27 registered G1 methods with
136 exact comparisons. That earlier result does not certify the combined current
source. Native lifecycle support at `d702b68d` passed 14728 CUDA checks across
four KV layouts using pattern data, plus 24605 host handle-registry checks and
sanitizer support. Pattern-data checks are separate from model equivalence.

All 16 registered G3 method bodies are included; the short draft run executes
only G3-004. Exhaustive page offsets, the remaining current-build model cases,
cumulative G1/G2/G3 and the FP16/INT8 execution matrix remain incomplete. INT8
has earlier isolated support but no completed independent baseline. No Windows
backend, HIP backend, power-loss, full-capacity stress or production guarantee
is asserted here.

Normal batched-prefill comparisons previously reached 1.5612177848815918 maximum
absolute logit error and were rejected. The measured draft uses the separately
pinned token-level operator; that result is not a tolerance for batched prefill.

## Run the reference checks

From this directory on Linux with Python 3:

```sh
python3 scripts/verify.py --gate G0
python3 examples/branching_demo.py
python3 scripts/mutation_smoke.py
```

These commands use the standard library and do not load a model. The acceptance
registry and unchanged required assertions are in `docs/acceptance.json` and
`docs/test-matrix.md`; missing tests, skips and expected failures cannot qualify
a gate.

## Run a model case

With an existing configured CUDA build, the native targets are `strata-branch`
and `strata-fresh`. Keep the independently built oracle separate from the SUT.
The native `branch_*` test targets provide the physical ownership and integrity
support checks; device-pressure programs are deliberately excluded from ordinary
parallel CTest runs.

Set `CTT_PROFILE` to a locally measured Strata execution profile that binds model
file hashes, executable hashes, hardware, execution arguments and the oracle.
Profiles are intentionally specific to a machine and build. The published
measurement summary is not an executable profile. Existing measured admission,
model-hash and calibration receipts can be checked with
`scripts/build_strata_profile.py`; profile provisioning is still a development
workflow.

```sh
CTT_PROFILE=/absolute/path/to/measured-profile.json \
  python3 scripts/run_ticket.py draft-branch-check \
  --gate G3 --pattern test_immutability.py
```

That unchanged case forces two different tokens through three consumed
generation boundaries per branch, compares each frontier to a completely fresh
full-history forward, audits every retained parent/sibling, and checks direct
forward counters. A one-case PASS is not a cumulative G3 PASS.

The source package preserves the tested API, registered tests, reference
equations and numerical assertions byte-for-byte. Host-specific orchestration
is excluded. One calibration helper now requires its existing `--native-root`
argument instead of supplying a private machine path; its mathematical rules
are unchanged. [The source manifest](evidence/source-manifest.json) records that
packaging boundary. Public evidence omits private paths and host identifiers;
the original artifact hashes and measurement scopes are retained.
