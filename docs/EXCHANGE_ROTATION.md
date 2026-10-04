# Resident expert exchange buffer rotation

When the resident RAM complement exchanges an expert with the GPU cache, the
evicted expert lands in a temporary host buffer. The existing path then copies
those bytes into the promoted expert's old RAM slot. Rotation removes that last
host copy: the temporary buffer becomes resident, and the old RAM slot becomes
the next temporary buffer.

## Enable

Rotation is **off by default**. Set `STRATA_EXCHANGE_ROTATE=1` before starting the
engine with your existing arguments:

```bash
export STRATA_EXCHANGE_ROTATE=1
```

```powershell
$env:STRATA_EXCHANGE_ROTATE = '1'
```

Only the exact value `1` opts in. Set it to `0` or remove it to restore the copy
path. This setting does not select resident RAM mode or change any preset.
It applies only when all layers have equal-size expert blocks, the resident
complement is fully pinned and GPU-mapped, and the exchange buffers can also be
pinned and mapped. Other layouts keep the copy path and log why rotation could
not be enabled. Configurations without a resident complement do not use it.

The startup diagnostic confirms activation:

```text
FileExpertSource: exchange buffer rotation enabled: ...; no host commit memcpy
```

Serving diagnostics report the cumulative rotated block count and avoided
`memcpy` payload bytes. This counts the copied payload once, not read plus write
traffic, and does not include the GPU transfers, which still occur.

## Experimental Q8 PLE tables

Q8 expert weights and the model's Q8 PLE lookup table are separate formats. The
Q8 PLE reader is an additional experiment, off by default. For a full Q8 model,
set `STRATA_EXPERIMENTAL_Q8_PLE=1` and use `--ple-io mmap` or `--ple-io ram`.
Without the exact value `1`, opening a Q8 PLE table fails with an explicit opt-in
message. Direct I/O for Q8 PLE is unsupported and is rejected.

This switch is independent of `STRATA_EXCHANGE_ROTATE`: keep Q8 PLE enabled in
both arms when comparing rotation on a Q8 model. The reader preserves the stored
Q8 scales and signed values. It uses the existing scalar dequantizer and mapped
reader; other PLE formats retain their existing paths.

With `STRATA_NATIVE_EXPERTS=ON`, `STRATA_BUILD_TESTS=ON` and CUDA configured:

```bash
cmake --build build --target ple_q8_parity
ctest --test-dir build -R '^ple_q8_selftest$' --output-on-failure
STRATA_EXPERIMENTAL_Q8_PLE=1 ./build/ple_q8_parity /path/to/shard-containing-Q8-PLE.gguf
```

The self-test needs no model or GPU. It compares decoded rows and batches with
ggml, including signed values, scales, page boundaries, malformed files,
close/reopen, mapped/RAM modes, and the opt-in gate.

## Ownership and synchronization

The original allocations own their memory until `FileExpertSource::close()`.
Rotation updates slot ownership and keeps each host pointer paired with its GPU
alias. Atomic slot IDs let background residency queries observe those immutable
pairs. Compute readers and GPU transfers must still finish before the existing
serialized commit; rotation adds no overlapping compute or new synchronization
policy. Reserve the maximum exchange capacity before rotation starts: growing a
live exchange arena is rejected because it can now hold resident experts.

## Tests

The ownership test can run without CUDA:

```bash
g++ -std=c++20 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -pthread -Iinclude tests/core/exchange_storage_test.cpp -o /tmp/exchange_storage_test
/tmp/exchange_storage_test
```

With an existing CUDA build configured:

```bash
cmake --build build --target strata exchange_storage_test file_expert_source_test
ctest --test-dir build -R '^(exchange_storage_test|file_expert_source_test)$' --output-on-failure
./build/file_expert_source_test --rotation-gpu
compute-sanitizer --tool memcheck --error-exitcode 71 ./build/file_expert_source_test --rotation-gpu
```

The CPU test checks byte preservation, pointer/alias ownership, guards, invalid
operations and concurrent residency queries across 12,304 exchanges. The CUDA
fixture performs 64 exchanges in each of three modes: copy with pinned RAM,
rotation with pinned RAM, and requested rotation with pageable RAM (fallback).
It checks exact bytes, GPU alias reads, file fallback, capacity, and close/reopen.
The GPU fixture is explicit; the ordinary CTest invocation does not run it.

On 2026-10-04, the clean patch on upstream
`6f32ec070f23ced9f50e704d854d775da52591ab` built on Linux with GCC 15.2 and CUDA
13.3 for an RTX 4090. Both CTest tests, the ASan/UBSan ownership test, and the
CUDA fixture passed. Compute Sanitizer reported **0 errors**. AMD and Windows
GPU execution were not tested for this patch.

## Three native token-identical comparisons

Measured on the clean branch at `aaff1617daf59954799f336960499cdc9970e356`,
based on upstream `6f32ec070f23ced9f50e704d854d775da52591ab`, on 2026-10-04.
The same Release binary was used for every arm: GCC 13.3, CUDA 13.2,
RTX PRO 6000 Blackwell 96GB, Ryzen 9 7950X, and 128GB installed RAM.
The fresh Blackwell build passed all four CTest checks, the three-mode CUDA
rotation fixture, and Compute Sanitizer (0 errors). On the actual Q8 PLE table,
1,059 row probes plus batch/issue-collect checks matched ggml bit-for-bit.

Every arm started a fresh engine with the same 1,024-token counting prompt,
40,960-token context allocation, FP16 KV, 16,400 GPU expert slots and 39.77 GiB
pinned/mapped resident expert complement. Expert weights and PLE use Q8_0;
the existing pack uses compatibility BF16 small projections and a Q5_K output
head. The PLE table was prefaulted into RAM but was not locked (`mlock` failed);
this is separate from the fully pinned expert complement required by rotation.

Both arms enable `STRATA_EXPERIMENTAL_Q8_PLE=1`. Only
`STRATA_EXCHANGE_ROTATE` changes. Decoding is greedy and target-only:
`--mtp-max-t 1 --suffix-draft 0`; upstream's serving loop still requires a
loaded MTP runtime. Each arm reported zero offered drafts and zero reused
prompt tokens. Adaptive exchanges wait for transfer completion.

| Generated tokens per arm | Rotation off, tokens/s | Rotation on, tokens/s | Rotated blocks | Avoided host-copy payload | Token IDs |
|---:|---:|---:|---:|---:|---|
| 1,024 | 58.06 | 62.07 | 2,549 | 13,311,897,600 bytes | Identical |
| 16,384 | 87.98 | 87.81 | 7,372 | 38,499,532,800 bytes | Identical |
| 32,768 | 90.00 | 91.73 | 9,341 | 48,782,438,400 bytes | Identical |

These are **generated output lengths**, each after the same 1,024-token input.
The test uses the out-of-vocabulary EOS sentinel `2147483647` to reach exact
lengths. This is a storage parity stress test, not an answer-quality benchmark.
Decode rates exclude model startup and prompt prefill. One pair per length on
one repetitive prompt does not establish a general speedup or speculative-path
parity. AMD and Windows GPU execution remain untested for this patch.

The [receipt](../bench/results/exchange-rotation-ab.json) records the source,
binary/model/profile hashes, full argument template, arm order, timings and
exchange counters. The [raw token IDs](../bench/results/exchange-rotation-token-ids.json)
contain the exact input and both outputs for all three pairs. Model hashes
are from the retained download manifest; file size/inode/mtime stability was
checked before each arm, without rehashing the large model files.

To verify the published token comparisons from the checkout, without a GPU:

```bash
python - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('bench/results')
r = json.loads((root / 'exchange-rotation-ab.json').read_text())
raw = (root / r['token_ids_file']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == r['token_ids_file_sha256']
ids = json.loads(raw)
for pair in r['comparisons']:
    n = pair['output_tokens']
    outputs = ids['outputs'][str(n)]
    assert outputs['off'] == outputs['on']
    for mode in ('off', 'on'):
        tokens = outputs[mode]
        assert len(tokens) == n
        digest = hashlib.sha256(json.dumps(tokens, separators=(',', ':')).encode()).hexdigest()
        assert digest == pair[mode]['output_token_ids_sha256']
    print(n, 'identical token IDs')
PY
```

To repeat generation, use the receipt's `args_template` with paths to your
prepared pack, its first native GGUF shard, MTP runtime and this source checkout.
Start one `StrataEngine` per arm with those arguments and the receipt's
`environment`, plus `STRATA_EXCHANGE_ROTATE=0` or `1`. Pass `ids['input']` to
`engine.generate(ids['input'], n, {'temperature': 0}, threading.Event())`,
collect every non-`None` token, and close the engine in `finally`. Require the
requested count, identical token arrays, zero offered drafts, nonzero resident
exchanges, and the activation/counter diagnostics above. This configuration
needs the stated memory capacity; it is not a general-purpose preset.
