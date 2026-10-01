# Experimental GR and MMVQ alternatives

This is a contribution to [Niko1221/Strata](https://github.com/Niko1221/Strata),
based on 0.1.33 (`aeb35be`). Strata's model support, expert cache and MTP are
upstream work. This patch changes two optional kernel launch paths.

**Validation of this focused patch is in progress. It is not ready for merging.**
Earlier measurements of a larger experimental branch motivated these candidates;
they are not measurements of this final source tree.

## Changes

- `STRATA_GR_DOWN_MAX4=1` specializes per-thread token storage for windows of
  at most four tokens. It preserves upstream's block size, tile selection,
  accumulation order and plain/split/staged choice. Larger windows retain the
  existing implementation. The parity test requires bitwise-identical outputs.
- `STRATA_MMVQ_WARP1=1` maps one warp to a dense MMVQ output row. This avoids
  a reduction between warps. Floating-point association changes, so numerical
  parity is checked with a declared relative-L1 limit of `1e-5`; exact output
  tokens are not promised. The observed use case is the consumer RX 5500 XT 8GB.

Both options are off by default. They do not change weights, quantization,
expert selection, or the MTP acceptance threshold. Test options individually.

This branch contains no hardware-enablement or non-MTP serving changes. To test
the RX 5500 XT, combine it with `contrib/gfx1012-community`. Non-MTP serving is
the independent `contrib/non-mtp-serving` contribution. Combined test commits
must be identified explicitly in the final results.

## Reproduction

Use upstream's build instructions for the relevant GPU with
`-DSTRATA_BUILD_TESTS=ON`, then build `strata`, `gr_roofline`, and `mmvq_roofline`.

```sh
./build/gr_roofline
./build/mmvq_roofline /path/to/IQ3_S-shard-1.gguf --all-shapes
STRATA_MMVQ_WARP1=1 STRATA_BENCH_ALLOW_ROUNDING=1 \
  ./build/mmvq_roofline /path/to/IQ3_S-shard-1.gguf --all-shapes
```

`tools/bench_mtp_modes.py` uses a local model config and fixed prompt token IDs.
Use `--mode on` on this independent branch. Testing `--mode off` also requires
the serving contribution. For example, allocate at least 70656 context tokens
in the config, and run:

```sh
python tools/bench_mtp_modes.py --config config.json --output result-64k \
  --input-tokens 65536 --output-tokens 4096 --workload long \
  --mode on --cases coding writing
```

The final matrix will include actual output lengths, prefill, first-token time,
generation rate, total completion time, effective throughput and correctness
checks. Model startup is excluded; the OS file cache is not reset. These are
execution measurements and functional smoke tests, not model-quality scores.
