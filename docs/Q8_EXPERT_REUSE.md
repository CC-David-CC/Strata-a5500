# Opt-in Q8 expert weight reuse

Target: full Unsloth Q8_0 on llm-60's RTX PRO 6000 Blackwell Workstation Edition
96 GB. This branch inherits the Q8 comparison harness. It is experimental and
defaults off; it has no new measured throughput result yet.

The existing grouped Q8 expert kernel loops through one token at a time. The
candidate loads one Q8 weight fragment and scale, then applies it to up to four
entries belonging to that same expert. It reuses the existing grouped IQ
kernel structure without changing expert selection, grouping, quantization,
accumulation order, or dense projection dispatch.

`STRATA_Q8_EXPERT_REUSE=1` enables the candidate. Zero/unset is the old path.
`STRATA_OLD_IQ_MMVQ=1` also forces the old path for differential testing.
Both the gate/up and down Q8 roles are covered. Other quant types are unchanged.

```sh
STRATA_Q8_EXPERT_REUSE=1 build/iq_multi_parity --q8-experts
STRATA_Q8_EXPERT_REUSE=1 compute-sanitizer --tool memcheck \
  build/iq_multi_parity --q8-experts
STRATA_Q8_EXPERT_REUSE=1 build/iq_multi_parity --q8-experts --bench
```

The fixture compares every written output and untouched destination bit for
bit, including empty groups, partial groups, repeated tokens and group sizes
through the compiled verifier limit. The benchmark rotates more than 600 MiB
of weights and reverses arm order. Component timing is not model throughput
or a measured DRAM-byte count.

The first model comparison must keep expert slots, RAM placement and prompts
fixed. Serial, MTP, n-gram and combined paths remain separate; singleton groups
may regress from extra control/index work even if larger groups improve.
Only a measured model gain should motivate broader integration. Q8 CPU misses
and PCIe transfer time can still dominate regardless of GPU kernel gains.
