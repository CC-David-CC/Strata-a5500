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
- A 4,096-node static graph with the same handshake.
- A 512 MiB read/modify/write payload. Two captured launches nominally move
  2 GiB; a declared 0.5–1.5 ratio allows L2 residency/deferred writeback while
  detecting missing or incorrectly scaled counters.

Every output word and marker count must be correct, with zero watchdog
interventions. After fixture success, a short model capture must match its
unprofiled control before attempting native 64K measurements.

Counters may be device scoped, so the runner yields to foreign GPU processes.
Profiled timings are not throughput evidence. CPU/PCIe constraints remain
separate from a GPU-only conditional bandwidth ceiling. This branch is pending
validation; it makes no new model speed or traffic claim.
