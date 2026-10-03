# Graph uploads in a counter range

This diagnostic branch addresses an Nsight Compute app-range replay failure on
llm-60 (RTX PRO 6000 Blackwell 96 GB, CUDA 13.2): prepared graphs were uploaded
before the profiling range, and replay rejected the range. No performance result
is claimed for this change.

`STRATA_PROFILE_GRAPH_UPLOADS=1` starts the profiler before explicitly uploading
the already prepared verifier and MTP graphs again. It requires decode skip zero
and graph preparation enabled. Uploading does not execute the model graphs.
Normal runs leave this setting off.

Measure two prefixes with identical setup, prompt, predictor, width and output
trajectory. Subtract their counters and divide by the committed positions between
their endpoints. Reject a pair if output tokens, window traces or graph creation
events disagree. The common uploads are setup, not useful token work; report them
and exclude them through prefix subtraction. Profiler throughput is never a
headline inference speed. Record the device planning mode because it can change
the path being measured.

First test oracle widths eight, four and two over the same 96 committed positions.
The supplied-answer oracle measures verifier capacity, not real predictor speed.
Only successful application replay and valid counters establish that this fixes
the capture problem.
