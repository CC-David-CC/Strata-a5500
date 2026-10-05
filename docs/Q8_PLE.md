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
