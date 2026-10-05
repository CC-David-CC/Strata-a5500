# Experimental Q8_0 PLE tables

The PLE lookup table is separate from the model's expert weights. This change
lets the existing mapped reader decode Q8_0 PLE rows with the existing scalar
Q8_0 dequantizer. Each 160-value row contains five 34-byte blocks, for 170 bytes.
It preserves the stored scales and signed values.

## Enable

The reader is off by default. Set the exact value `1` in the engine's environment:

```bash
export STRATA_EXPERIMENTAL_Q8_PLE=1
```

```powershell
$env:STRATA_EXPERIMENTAL_Q8_PLE = '1'
```

Use the prepared model's Q8_0 PLE shard with `--ple-io mmap` or `--ple-io ram`.
The engine's existing native-model configuration and pack are still required;
this change adds no installer model choice or hardware preset. Without the
opt-in, opening a Q8 PLE table reports the required flag. Q8 direct I/O is
unsupported and is rejected explicitly. Existing PLE formats keep their paths.

The original table has 320,001,536 rows: Q8_0 stores about 50.66 GiB of row data.
RAM prefaulting therefore needs substantial memory. `mmap` and `ram` retain
their existing memory and locking behavior; this reader does not manage GPU
placement or select a cache budget.

## Tests

With CUDA, `STRATA_NATIVE_EXPERTS=ON` and `STRATA_BUILD_TESTS=ON` configured:

```bash
cmake --build build --target strata ple_q8_parity ple_reader_test
ctest --test-dir build -R '^(ple_q8_selftest|ple_reader_selftest)$' --output-on-failure
STRATA_EXPERIMENTAL_Q8_PLE=1 ./build/ple_q8_parity /path/to/shard-containing-Q8-PLE.gguf
```

The Q8 self-test needs no model or GPU execution. It checks exact flag values,
signed/scaled rows against ggml, page boundaries, mapped/RAM modes, row/batch
and issue/collect reads, malformed shapes and file lengths, out-of-range reads,
and close/reopen. The real-table command compares 1,059 row probes and batch
results with ggml. Size arithmetic and tensor extents are checked before use.

## Recorded validation

The independent reader commit `18d3da487f82c8e7b5d8e91f6fdd8c75972182f1` was freshly
built and tested on 2026-10-05 (UTC), based on upstream
`6f32ec070f23ced9f50e704d854d775da52591ab`. It contains no buffer rotation code.
Hardware: RTX PRO 6000 Blackwell 96GB, Ryzen 9 7950X, 128GB RAM;
Release build with GCC 13.3 and CUDA 13.2.

Both CTest checks passed. On the model's Q8 PLE table, all 1,059 row probes and
batch/issue-collect results matched ggml bit-for-bit. A fresh native engine
generated exactly 1,024 tokens after the retained 1,024-token input. All output
IDs matched the earlier combined build's rotation-off baseline. The fresh run
offered zero speculative drafts and reused zero prompt tokens.

The model uses Q8_0 experts and PLE, compatibility BF16 small projections and a
Q5_K output head. The smoke run uses FP16 KV, 16,400 GPU expert slots and a
39.77 GiB pinned expert complement. PLE was prefaulted but not mlocked. The EOS
sentinel forces the exact output length. This verifies the reader in a native
run; it is not an answer-quality evaluation or a timed performance comparison.
AMD and Windows GPU execution remain untested.

The [receipt](../bench/results/q8-ple-reader-validation.json) records source,
binary/model/profile hashes, arguments and test results. The
[token arrays](../bench/results/q8-ple-reader-token-ids.json) retain the input,
fresh output and reference output. To check them without a GPU:

```bash
python - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('bench/results')
r = json.loads((root / 'q8-ple-reader-validation.json').read_text())
raw = (root / r['token_ids_file']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == r['token_ids_file_sha256']
ids = json.loads(raw)
assert len(ids['input']) == len(ids['output']) == len(ids['reference']) == 1024
assert ids['output'] == ids['reference']
print('1,024 matching native output token IDs')
PY
```

## Relationship to rotation

This reader has no dependency on the resident-buffer rotation contribution
in [PR #864](https://github.com/Niko1221/Strata/pull/864). It changes neither
the expert source nor the generation loop. Its implementation is extracted
from the reader tested at `aaff1617daf59954799f336960499cdc9970e356`.

The earlier combined branch has published
[1K, 16K and 32K generated-token comparisons](https://github.com/CC-David-CC/Strata-a5500/blob/99b5c6fd2d0de385e34328e0be28e67c19c0cce1/docs/EXCHANGE_ROTATION.md#three-native-token-identical-comparisons)
and [raw token IDs](https://github.com/CC-David-CC/Strata-a5500/blob/99b5c6fd2d0de385e34328e0be28e67c19c0cce1/bench/results/exchange-rotation-token-ids.json).
Those runs enabled Q8 PLE in both arms and changed only rotation. They measure
storage parity for that combined build, not a speedup from the Q8 reader.
