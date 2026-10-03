# Direct Q8 counter collection

Local diagnostic branch `diag/q8-cupti-user-range`, based on the tested ownership
engine `1a50d913`. No engine sources or model kernels are changed. Hardware:
RTX PRO 6000 Blackwell Workstation Edition 96 GB, 128 GB RAM, Linux, CUDA 13.2.

Nsight Compute 2026.1.1 rejected repeated static graph launches in a small
app-range fixture. Fresh graph instances fixed that fixture, but the full Q8
probe still blocked inside its first `cudaGraphLaunch`, before the requested
range. The unprofiled fresh-graph model matched the frozen engine's 128 output
tokens; the profiled run was released by the existing watchdog. No model
counter result was accepted. The dependent 64K matrix did not run.

This alternative uses a private `LD_PRELOAD` library that implements only
`cudaProfilerStart` and `cudaProfilerStop`. Those existing opt-in range markers
initialize the installed CUPTI range API, collect one user range in one pass,
and write the evaluated byte counters plus raw counter/config images. It does
not intercept graph launch, replace graphs, replay model work, control clocks
or change model precision. The shared CUDA runtime is required.

The API sequence follows NVIDIA's installed `range_profiling` sample and
[CUPTI documentation](https://docs.nvidia.com/cupti/main/main.html).
Only the three requested metrics are scheduled: DRAM read bytes, DRAM write
bytes and L2 transaction bytes. Multiple passes, dropped ranges, invalid values
and missing capture are rejected. A fresh process is required per capture.

## Gates

`tools/profile_q8_cupti_fixture.py` builds the library and a bounded fixture
under the private fleet queue. Each shape runs with and without the library:

- A small static graph with a mapped CPU/GPU handshake.
- A static graph with 4,096 marker nodes plus handshake and payload nodes.
- A 512 MiB read/modify/write payload. Two captured launches nominally move
  2 GiB; a declared 0.5–1.5 ratio allows L2 residency/deferred writeback while
  detecting missing or incorrectly scaled counters.

Every output word and marker count must be correct, with zero watchdog
interventions. After fixture success, a short model capture must match its
unprofiled control before attempting native 64K measurements.

Counters may be device scoped, so the runner yields to foreign GPU processes.
Profiled timings are not throughput evidence. CPU/PCIe constraints remain
separate from a GPU-only conditional bandwidth ceiling.

## Fixture result, 2026-10-03

All six control/profile cases passed on source `06d5f4fc`: every output word and
marker count matched, with zero watchdog interventions. Each direct capture
used one pass and one range with zero dropped ranges. The large-payload test
measured 1,073,826,048 DRAM read bytes and 1,058,195,712 write bytes: **99.28%**
of the nominal 2 GiB. Small payloads mostly stayed in L2, as expected.

The measured library SHA-256 is
`47d059ca1cc9040caf2247ff5fd6620eb460c0fe5125cf3397f5b19e41012450`.
`tools/profile_q8_cupti_model.py` verifies that library and the frozen ownership
binary, then compares an 8K/128-output capture against the just-completed 8K
control. Only after equality does it attempt the native 64K/512-output matrix.
Model counter results are pending; no new model speed claim follows yet.
