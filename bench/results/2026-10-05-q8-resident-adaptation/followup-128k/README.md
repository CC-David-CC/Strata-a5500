# 128K and Q8 cancellation/recovery follow-up

Same code and binary as the published Q8 adaptation experiment: code `07ff95b`,
published branch head `3d0d38d`. RTX PRO 6000 Blackwell Workstation 96 GB,
Ryzen 9 7950X / 128 GB RAM; Q8 experts/PLE, compatibility dense pack, FP16 KV,
MTP T4, async + rotation + duplex + per-layer admission; locked PLE.

## Completed 128K request

| Measurement | Result |
| --- | ---: |
| Actual input | 131,072 tokens, none reused |
| Output | 1,024 tokens; stopped at requested length |
| Decode | **141.115 tok/s** |
| Prefill | 213.195 s |
| Generation | 7.2565 s |
| Request wall time | 220.487 s |
| Output / full request wall time | 4.644 tok/s |
| Startup, excluded from request time | 122.344 s |

This is one successful longer-input run. It is not a new upstream or rotation
on/off comparison, and establishes no new percentage gain at 128K.

## Cancellation/recovery qualification

The 4K editing stream delivered 128 tokens before cancellation; the engine
reported 135 generated positions and `finish=cancel` as in-flight work drained.
A following request in that engine completed all 512 requested tokens at
134.021 tok/s. A fresh engine completed the same prompt/output length at
126.972 tok/s. Output first differed at zero-based token index **43**; recorded
work also differed. These speeds describe different work, not a cancellation
performance gain.

The engine recovered operationally. Exact state equivalence is **not proved**:
cache/adaptation history and CPU/GPU arithmetic placement can differ, but this
screen does not rule out state contamination. A placement-controlled comparison
and/or state digest trace is needed to distinguish those explanations.

## Evidence

- [Readable summary](summary.json)
- [Original plans, harness, inputs/outputs and logs](followup-history.tar.gz)
- [Per-file hash manifest](followup-manifest.json)

Archive hashes, full input/output lengths and feature activation were verified
before publication. The full three-case job exited zero in 628.8 seconds.
The LAN service remained stopped and disabled; no production endpoint changed.
