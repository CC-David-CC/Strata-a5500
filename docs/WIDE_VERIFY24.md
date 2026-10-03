# Verifier windows beyond eight

Experimental on llm-60: RTX PRO 6000 Blackwell 96 GB (SM120), 128 GB RAM,
full-expert Unsloth UD-Q4_K_XL. No speed or correctness claim before testing.

Configure `-DSTRATA_VERIFY_MAX_T=24`. The default remains eight. Runtime
`--spec` allocates the window, `--mtp-max-t` controls draft depth, and the
diagnostic width controls can limit work within the allocation. Compare
12, 16, 18 and 24 with eight on identical prompts and output budgets.

## What changed

- One capacity constant covers verifier token arrays, graph handles, policy
  estimates, recurrent scratch, CPU expert work and MTP graph handles.
- MTP quantized activation scratch now holds the full window. Its former
  fixed allocation of eight rows was insufficient for larger projections.
- Native MMVQ dispatch supports every width through 24, including tails.
  BF16 and IQ projections support the larger column counts too.
- Resident grouping and hit selection hold 256 entries, enough for 24 x 10
  routed experts. Pointer rebasing traverses all entries.
- S2 grouped gate/up activations use opt-in dynamic shared memory above
  eight: 69,120 bytes for the old layout and 76,800 for the newer layout.
  Setup validates the hardware limit before model graph capture. This
  experimental build is not intended for cards with smaller limits.

Some numbers are tiles, not capacity limits. CPU AVX2 retains its eight-row
register tile and processes all remaining rows. MTP fc_hidden also tiles
eight rows. The existing grouped IQ expert kernels traverse all entries in
tiles of four. Hyper-connection down kernels split tokens as required by
the device shared-memory limit; their up kernels cover the whole window.
Q8 row grouping eight uses four output rows beyond 16 columns to stay within
48 KiB static shared memory, while retaining every token column.

## Gates before timing

Native MMVQ and BF16 compare each wide column against an independent
single-column call, bit for bit, including unused output tails. Grouped S2
checks exercise maximum-size groups, more than 128 entries and resident
grouping. IQ checks compare the previous per-column implementation with
all widths and large expert groups. Hyper-connection initialization checks
every token count through the compiled limit.

Then compare target tokens and committed KV/recurrent/history state at
output caps around the window boundaries, full oracle acceptance, forced
rejection at early/middle/late positions, and real MTP at wide depth. The
oracle receives the known answer and stopping length; it measures verifier
capacity, not usable inference. Report it separately from all real paths.

Run short 8K gates before 64K measurements. Keep decode, setup, prefill and
effective rates separate. Record memory use and actual width/acceptance
histograms. A larger buffer allocation alone is not a larger effective batch.
