# Complete retained Q8 hillclimb observations

Frozen at the user-requested pause. See [summary, definitions and selected
profiles](Q8_FROZEN_MATRIX.md) first. Tables retain all completed observations,
including controls and negative results. Diagnostic traces/profilers change
timing and are labeled; do not rank them as production speed. Each record's
full flags, source, binary hash, actual token count, timings and comparison
are in the machine-readable artifact. Input/output sizes can differ in earlier
records; the actual output count is retained there.

## cache-followups-live.json rtxpro-q8-readonly-followup-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-readonly-4-repeat | 32,768 | 1,024 | MTP | coding | 132.64 | 65.44 | 4136.12 | 7.92 | 15.64 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-4-repeat | 32,768 | 1,024 | MTP | editing | 113.69 | 61.06 | 4222.84 | 7.76 | 16.77 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-0-repeat | 32,768 | 1,024 | MTP | coding | 129.94 | 64.83 | 4142.03 | 7.91 | 15.79 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-0-repeat | 32,768 | 1,024 | MTP | editing | 112.14 | 60.59 | 4221.10 | 7.76 | 16.89 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-8 | 32,768 | 1,024 | MTP | coding | 132.80 | 65.49 | 4137.11 | 7.92 | 15.63 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-8 | 32,768 | 1,024 | MTP | editing | 115.63 | 61.61 | 4223.17 | 7.76 | 16.62 | Exact output and recorded work versus paired control |
| 32768-mtp-primary-plus192 | 32,768 | 1,024 | MTP | coding | 130.19 | 65.35 | 4201.19 | 7.80 | 15.67 | * First output difference at token 13; work may differ |
| 32768-mtp-primary-plus192 | 32,768 | 1,024 | MTP | editing | 115.04 | 62.03 | 4310.05 | 7.60 | 16.50 | * Matching output; speculative work differs |
| 32768-ngram-readonly-4-repeat | 32,768 | 1,024 | Plain+ngram | coding | 78.98 | 49.11 | 4157.37 | 7.88 | 20.85 | * First output difference at token 120; work may differ |
| 32768-ngram-readonly-4-repeat | 32,768 | 1,024 | Plain+ngram | editing | 114.25 | 61.33 | 4239.73 | 7.73 | 16.69 | * Matching output; speculative work differs |
| 32768-ngram-readonly-0-repeat | 32,768 | 1,024 | Plain+ngram | coding | 77.17 | 48.39 | 4154.84 | 7.89 | 21.16 | * First output difference at token 120; work may differ |
| 32768-ngram-readonly-0-repeat | 32,768 | 1,024 | Plain+ngram | editing | 105.00 | 58.62 | 4249.79 | 7.71 | 17.46 | * Matching output; speculative work differs |
| 131072-plain-readonly-0 | 131,072 | 1,024 | Plain | coding | 74.74 | 22.33 | 4078.18 | 32.14 | 45.84 | Reference / no paired check in this record |
| 131072-plain-readonly-0 | 131,072 | 1,024 | Plain | editing | 59.69 | 20.81 | 4092.85 | 32.02 | 49.18 | Reference / no paired check in this record |
| 131072-plain-readonly-4 | 131,072 | 1,024 | Plain | coding | 75.00 | 22.37 | 4082.99 | 32.10 | 45.76 | Exact output and recorded work versus paired control |
| 131072-plain-readonly-4 | 131,072 | 1,024 | Plain | editing | 60.20 | 20.87 | 4090.44 | 32.04 | 49.05 | Exact output and recorded work versus paired control |
| 131072-mtp-readonly-0 | 131,072 | 1,024 | MTP | coding | 132.18 | 25.66 | 4076.74 | 32.15 | 39.90 | Reference / no paired check in this record |
| 131072-mtp-readonly-0 | 131,072 | 1,024 | MTP | editing | 106.52 | 24.54 | 4083.32 | 32.10 | 41.71 | Reference / no paired check in this record |
| 131072-mtp-readonly-4 | 131,072 | 1,024 | MTP | coding | 133.97 | 25.71 | 4074.17 | 32.17 | 39.81 | Exact output and recorded work versus paired control |
| 131072-mtp-readonly-4 | 131,072 | 1,024 | MTP | editing | 107.95 | 24.63 | 4086.86 | 32.07 | 41.56 | Exact output and recorded work versus paired control |
| 131072-ngram-readonly-0 | 131,072 | 1,024 | Plain+ngram | coding | 74.37 | 22.29 | 4077.40 | 32.15 | 45.92 | Reference / no paired check in this record |
| 131072-ngram-readonly-0 | 131,072 | 1,024 | Plain+ngram | editing | 100.80 | 24.29 | 4097.83 | 31.99 | 42.14 | Reference / no paired check in this record |
| 131072-ngram-readonly-4 | 131,072 | 1,024 | Plain+ngram | coding | 76.18 | 22.48 | 4083.67 | 32.10 | 45.54 | * First output difference at token 452; work may differ |
| 131072-ngram-readonly-4 | 131,072 | 1,024 | Plain+ngram | editing | 103.05 | 24.40 | 4094.93 | 32.01 | 41.95 | * Matching output; speculative work differs |
| 131072-mtp-ngram-readonly-0 | 131,072 | 1,024 | MTP+ngram | coding | 131.68 | 25.62 | 4074.67 | 32.17 | 39.94 | Reference / no paired check in this record |
| 131072-mtp-ngram-readonly-0 | 131,072 | 1,024 | MTP+ngram | editing | 103.49 | 24.39 | 4085.68 | 32.08 | 41.98 | Reference / no paired check in this record |
| 131072-mtp-ngram-readonly-4 | 131,072 | 1,024 | MTP+ngram | coding | 133.49 | 25.71 | 4078.67 | 32.14 | 39.81 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-readonly-4 | 131,072 | 1,024 | MTP+ngram | editing | 105.51 | 24.49 | 4084.73 | 32.09 | 41.79 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-miss-overlap-validation-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-plain-overlap0-ways0 | 32,768 | 1,024 | Plain | coding | 73.82 | 47.00 | 4143.44 | 7.91 | 21.78 | Exact output and recorded work versus paired control |
| 32768-plain-overlap0-ways0 | 32,768 | 1,024 | Plain | editing | 62.01 | 42.25 | 4244.94 | 7.72 | 24.23 | Exact output and recorded work versus paired control |
| 32768-plain-overlap1-ways0 | 32,768 | 1,024 | Plain | coding | 73.52 | 46.95 | 4158.32 | 7.88 | 21.81 | Exact output and recorded work versus paired control |
| 32768-plain-overlap1-ways0 | 32,768 | 1,024 | Plain | editing | 62.10 | 42.29 | 4244.50 | 7.72 | 24.21 | Exact output and recorded work versus paired control |
| 32768-plain-overlap0-ways4 | 32,768 | 1,024 | Plain | coding | 74.02 | 47.13 | 4153.32 | 7.89 | 21.72 | Exact output and recorded work versus paired control |
| 32768-plain-overlap0-ways4 | 32,768 | 1,024 | Plain | editing | 62.49 | 42.47 | 4243.84 | 7.72 | 24.11 | Exact output and recorded work versus paired control |
| 32768-plain-overlap1-ways4 | 32,768 | 1,024 | Plain | coding | 74.22 | 47.23 | 4157.80 | 7.88 | 21.68 | Exact output and recorded work versus paired control |
| 32768-plain-overlap1-ways4 | 32,768 | 1,024 | Plain | editing | 62.64 | 42.54 | 4243.41 | 7.72 | 24.07 | Exact output and recorded work versus paired control |
| 32768-mtp-overlap0-ways0 | 32,768 | 1,024 | MTP | coding | 130.03 | 64.66 | 4118.34 | 7.96 | 15.83 | Exact output and recorded work versus paired control |
| 32768-mtp-overlap0-ways0 | 32,768 | 1,024 | MTP | editing | 112.10 | 60.61 | 4225.08 | 7.76 | 16.89 | Exact output and recorded work versus paired control |
| 32768-mtp-overlap1-ways0 | 32,768 | 1,024 | MTP | coding | 130.10 | 64.70 | 4121.29 | 7.95 | 15.82 | Exact output and recorded work versus paired control |
| 32768-mtp-overlap1-ways0 | 32,768 | 1,024 | MTP | editing | 113.00 | 60.87 | 4225.40 | 7.75 | 16.82 | Exact output and recorded work versus paired control |
| 32768-mtp-overlap0-ways4 | 32,768 | 1,024 | MTP | coding | 132.58 | 65.46 | 4140.62 | 7.91 | 15.64 | Exact output and recorded work versus paired control |
| 32768-mtp-overlap0-ways4 | 32,768 | 1,024 | MTP | editing | 113.67 | 61.04 | 4221.10 | 7.76 | 16.77 | Exact output and recorded work versus paired control |
| 32768-mtp-overlap1-ways4 | 32,768 | 1,024 | MTP | coding | 132.64 | 65.30 | 4118.55 | 7.96 | 15.68 | Exact output and recorded work versus paired control |
| 32768-mtp-overlap1-ways4 | 32,768 | 1,024 | MTP | editing | 115.29 | 61.53 | 4224.64 | 7.76 | 16.64 | Exact output and recorded work versus paired control |
| 32768-ngram-overlap0-ways0 | 32,768 | 1,024 | Plain+ngram | coding | 77.01 | 48.28 | 4145.33 | 7.90 | 21.20 | * First output difference at token 120; work may differ |
| 32768-ngram-overlap0-ways0 | 32,768 | 1,024 | Plain+ngram | editing | 106.21 | 58.93 | 4239.62 | 7.73 | 17.37 | * Matching output; speculative work differs |
| 32768-ngram-overlap1-ways0 | 32,768 | 1,024 | Plain+ngram | coding | 75.25 | 47.63 | 4154.53 | 7.89 | 21.49 | * First output difference at token 316; work may differ |
| 32768-ngram-overlap1-ways0 | 32,768 | 1,024 | Plain+ngram | editing | 105.55 | 58.75 | 4243.41 | 7.72 | 17.42 | * Matching output; speculative work differs |
| 32768-ngram-overlap0-ways4 | 32,768 | 1,024 | Plain+ngram | coding | 74.65 | 47.32 | 4138.94 | 7.92 | 21.63 | * First output difference at token 120; work may differ |
| 32768-ngram-overlap0-ways4 | 32,768 | 1,024 | Plain+ngram | editing | 108.45 | 59.59 | 4235.84 | 7.74 | 17.18 | * Matching output; speculative work differs |
| 32768-ngram-overlap1-ways4 | 32,768 | 1,024 | Plain+ngram | coding | 75.53 | 47.70 | 4145.38 | 7.90 | 21.46 | * First output difference at token 564; work may differ |
| 32768-ngram-overlap1-ways4 | 32,768 | 1,024 | Plain+ngram | editing | 116.52 | 62.06 | 4251.17 | 7.71 | 16.50 | * Matching output; speculative work differs |
| 32768-mtp-ngram-overlap0-ways0 | 32,768 | 1,024 | MTP+ngram | coding | 130.58 | 64.94 | 4136.28 | 7.92 | 15.76 | * First output difference at token 122; work may differ |
| 32768-mtp-ngram-overlap0-ways0 | 32,768 | 1,024 | MTP+ngram | editing | 113.66 | 61.10 | 4230.48 | 7.75 | 16.75 | * Matching output; speculative work differs |
| 32768-mtp-ngram-overlap1-ways0 | 32,768 | 1,024 | MTP+ngram | coding | 129.78 | 64.67 | 4127.21 | 7.94 | 15.83 | * First output difference at token 311; work may differ |
| 32768-mtp-ngram-overlap1-ways0 | 32,768 | 1,024 | MTP+ngram | editing | 111.29 | 60.34 | 4219.47 | 7.77 | 16.97 | * Matching output; speculative work differs |
| 32768-mtp-ngram-overlap0-ways4 | 32,768 | 1,024 | MTP+ngram | coding | 133.15 | 65.58 | 4137.84 | 7.92 | 15.61 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-overlap0-ways4 | 32,768 | 1,024 | MTP+ngram | editing | 115.35 | 61.52 | 4220.61 | 7.76 | 16.64 | * Matching output; speculative work differs |
| 32768-mtp-ngram-overlap1-ways4 | 32,768 | 1,024 | MTP+ngram | coding | 134.18 | 65.76 | 4128.93 | 7.94 | 15.57 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-overlap1-ways4 | 32,768 | 1,024 | MTP+ngram | editing | 114.47 | 61.25 | 4219.09 | 7.77 | 16.71 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-miss-overlap-profile-20261004

**Diagnostic: timings are not comparable serving benchmarks.**

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-stageprofile-overlap0-ways0 | 32,768 | 512 | MTP | coding | 115.44 | 41.44 | 4139.20 | 7.92 | 12.35 | Reference / no paired check in this record |
| 32768-mtp-stageprofile-overlap0-ways0 | 32,768 | 512 | MTP | editing | 82.10 | 36.58 | 4224.86 | 7.76 | 13.99 | Reference / no paired check in this record |
| 32768-mtp-stageprofile-overlap1-ways0 | 32,768 | 512 | MTP | coding | 115.70 | 41.47 | 4138.68 | 7.92 | 12.34 | Exact output and recorded work versus paired control |
| 32768-mtp-stageprofile-overlap1-ways0 | 32,768 | 512 | MTP | editing | 82.26 | 36.61 | 4224.48 | 7.76 | 13.98 | Exact output and recorded work versus paired control |
| 32768-mtp-stageprofile-overlap0-ways4 | 32,768 | 512 | MTP | coding | 118.32 | 41.81 | 4140.98 | 7.91 | 12.24 | Reference / no paired check in this record |
| 32768-mtp-stageprofile-overlap0-ways4 | 32,768 | 512 | MTP | editing | 83.84 | 36.91 | 4222.46 | 7.76 | 13.87 | Reference / no paired check in this record |
| 32768-mtp-stageprofile-overlap1-ways4 | 32,768 | 512 | MTP | coding | 119.70 | 41.97 | 4139.26 | 7.92 | 12.19 | Exact output and recorded work versus paired control |
| 32768-mtp-stageprofile-overlap1-ways4 | 32,768 | 512 | MTP | editing | 85.29 | 37.21 | 4226.11 | 7.75 | 13.76 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-cpu-reuse-model-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-cpu-reuse0-ways4 | 32,768 | 1,024 | MTP | coding | 132.68 | 65.49 | 4141.61 | 7.91 | 15.63 | Reference / no paired check in this record |
| 32768-mtp-cpu-reuse0-ways4 | 32,768 | 1,024 | MTP | editing | 113.71 | 61.06 | 4222.52 | 7.76 | 16.77 | Reference / no paired check in this record |
| 32768-mtp-cpu-reuse1-ways4 | 32,768 | 1,024 | MTP | coding | 131.73 | 65.24 | 4138.31 | 7.92 | 15.69 | Exact output and recorded work versus paired control |
| 32768-mtp-cpu-reuse1-ways4 | 32,768 | 1,024 | MTP | editing | 113.63 | 61.03 | 4221.97 | 7.76 | 16.77 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-miss-overlap-profile-20261004-r3

**Diagnostic: timings are not comparable serving benchmarks.**

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-stageprofile-overlap0-ways4 | 32,768 | 1,024 | MTP | coding | 129.70 | 64.67 | 4129.66 | 7.93 | 15.83 | Reference / no paired check in this record |
| 32768-mtp-stageprofile-overlap0-ways4 | 32,768 | 1,024 | MTP | editing | 112.09 | 60.57 | 4219.91 | 7.77 | 16.90 | Reference / no paired check in this record |
| 32768-mtp-stageprofile-overlap1-ways4 | 32,768 | 1,024 | MTP | coding | 129.90 | 64.78 | 4138.73 | 7.92 | 15.80 | Exact output and recorded work versus paired control |
| 32768-mtp-stageprofile-overlap1-ways4 | 32,768 | 1,024 | MTP | editing | 114.08 | 61.17 | 4222.46 | 7.76 | 16.74 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-cpu-reuse-other-modes-20261004-r2

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-ngram-cpu-reuse0-ways4 | 32,768 | 1,024 | Plain+ngram | coding | 78.95 | 49.02 | 4141.09 | 7.91 | 20.88 | Reference / no paired check in this record |
| 32768-ngram-cpu-reuse0-ways4 | 32,768 | 1,024 | Plain+ngram | editing | 112.58 | 60.91 | 4249.13 | 7.71 | 16.81 | Reference / no paired check in this record |
| 32768-ngram-cpu-reuse1-ways4 | 32,768 | 1,024 | Plain+ngram | coding | 77.25 | 48.37 | 4143.49 | 7.91 | 21.16 | * First output difference at token 120; work may differ |
| 32768-ngram-cpu-reuse1-ways4 | 32,768 | 1,024 | Plain+ngram | editing | 102.70 | 57.82 | 4236.93 | 7.73 | 17.70 | * Matching output; speculative work differs |
| 32768-mtp-ngram-cpu-reuse0-ways4 | 32,768 | 1,024 | MTP+ngram | coding | 131.08 | 65.10 | 4141.66 | 7.91 | 15.72 | Reference / no paired check in this record |
| 32768-mtp-ngram-cpu-reuse0-ways4 | 32,768 | 1,024 | MTP+ngram | editing | 111.72 | 60.44 | 4216.11 | 7.77 | 16.94 | Reference / no paired check in this record |
| 32768-mtp-ngram-cpu-reuse1-ways4 | 32,768 | 1,024 | MTP+ngram | coding | 132.37 | 65.22 | 4116.63 | 7.96 | 15.70 | * First output difference at token 311; work may differ |
| 32768-mtp-ngram-cpu-reuse1-ways4 | 32,768 | 1,024 | MTP+ngram | editing | 111.84 | 60.50 | 4220.67 | 7.76 | 16.92 | * Matching output; speculative work differs |
| 32768-plain-cpu-reuse0-ways4 | 32,768 | 1,024 | Plain | coding | 74.33 | 47.30 | 4164.03 | 7.87 | 21.64 | Reference / no paired check in this record |
| 32768-plain-cpu-reuse0-ways4 | 32,768 | 1,024 | Plain | editing | 62.53 | 42.49 | 4244.50 | 7.72 | 24.10 | Reference / no paired check in this record |
| 32768-plain-cpu-reuse1-ways4 | 32,768 | 1,024 | Plain | coding | 74.27 | 47.30 | 4171.29 | 7.86 | 21.64 | Exact output and recorded work versus paired control |
| 32768-plain-cpu-reuse1-ways4 | 32,768 | 1,024 | Plain | editing | 62.50 | 42.47 | 4243.02 | 7.72 | 24.11 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-miss-geometry-model-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-grid384-overlap0-ways4 | 32,768 | 1,024 | MTP | coding | 131.93 | 65.30 | 4140.25 | 7.91 | 15.68 | Reference / no paired check in this record |
| 32768-mtp-grid384-overlap0-ways4 | 32,768 | 1,024 | MTP | editing | 113.66 | 61.05 | 4223.33 | 7.76 | 16.77 | Reference / no paired check in this record |
| 32768-mtp-grid384-overlap1-ways4 | 32,768 | 1,024 | MTP | coding | 133.75 | 65.72 | 4136.85 | 7.92 | 15.58 | Exact output and recorded work versus paired control |
| 32768-mtp-grid384-overlap1-ways4 | 32,768 | 1,024 | MTP | editing | 115.86 | 61.68 | 4222.46 | 7.76 | 16.60 | Exact output and recorded work versus paired control |
| 32768-mtp-grid96-overlap0-ways4 | 32,768 | 1,024 | MTP | coding | 132.99 | 65.40 | 4120.15 | 7.95 | 15.65 | Exact output and recorded work versus paired control |
| 32768-mtp-grid96-overlap0-ways4 | 32,768 | 1,024 | MTP | editing | 114.48 | 61.28 | 4222.19 | 7.76 | 16.71 | Exact output and recorded work versus paired control |
| 32768-mtp-grid96-overlap1-ways4 | 32,768 | 1,024 | MTP | coding | 134.03 | 65.69 | 4124.51 | 7.94 | 15.58 | Exact output and recorded work versus paired control |
| 32768-mtp-grid96-overlap1-ways4 | 32,768 | 1,024 | MTP | editing | 117.04 | 62.01 | 4223.12 | 7.76 | 16.51 | Exact output and recorded work versus paired control |
| 32768-mtp-grid32-overlap0-ways4 | 32,768 | 1,024 | MTP | coding | 132.66 | 65.32 | 4120.52 | 7.95 | 15.67 | Exact output and recorded work versus paired control |
| 32768-mtp-grid32-overlap0-ways4 | 32,768 | 1,024 | MTP | editing | 115.68 | 61.64 | 4224.69 | 7.76 | 16.61 | Exact output and recorded work versus paired control |
| 32768-mtp-grid32-overlap1-ways4 | 32,768 | 1,024 | MTP | coding | 133.87 | 65.59 | 4118.29 | 7.96 | 15.61 | Exact output and recorded work versus paired control |
| 32768-mtp-grid32-overlap1-ways4 | 32,768 | 1,024 | MTP | editing | 118.50 | 62.43 | 4224.20 | 7.76 | 16.40 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-host-dram-decode-20261004

**Diagnostic: timings are not comparable serving benchmarks.**

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-coding-serial-control | 32,768 | 1,024 | MTP | coding | 132.64 | 65.31 | 4119.17 | 7.96 | 15.67 | Reference / no paired check in this record |
| 32768-mtp-coding-serial-UMC | 32,768 | 1,024 | MTP | coding | 57.11 | 34.55 | 2801.31 | 11.70 | 29.63 | Exact output and recorded work versus paired control |
| 32768-mtp-coding-overlap-UMC | 32,768 | 1,024 | MTP | coding | 55.41 | 33.82 | 2779.02 | 11.79 | 30.27 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-seeded-ram-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-profile-tail-seed0 | 32,768 | 1,024 | MTP | coding | 130.41 | 64.93 | 4140.67 | 7.91 | 15.77 | Reference / no paired check in this record |
| 32768-mtp-profile-tail-seed0 | 32,768 | 1,024 | MTP | editing | 112.04 | 60.57 | 4221.05 | 7.76 | 16.90 | Reference / no paired check in this record |
| 32768-mtp-profile-tail-seed1 | 32,768 | 1,024 | MTP | coding | 129.94 | 64.88 | 4149.21 | 7.90 | 15.78 | Exact output and recorded work versus paired control |
| 32768-mtp-profile-tail-seed1 | 32,768 | 1,024 | MTP | editing | 111.88 | 60.54 | 4223.71 | 7.76 | 16.91 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-miss-geometry-followup-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-repeat-grid32-overlap1 | 32,768 | 1,024 | MTP | coding | 134.88 | 66.04 | 4143.34 | 7.91 | 15.50 | Exact output and recorded work versus paired control |
| 32768-mtp-repeat-grid32-overlap1 | 32,768 | 1,024 | MTP | editing | 118.34 | 62.45 | 4233.70 | 7.74 | 16.39 | Exact output and recorded work versus paired control |
| 32768-mtp-repeat-grid32-overlap0 | 32,768 | 1,024 | MTP | coding | 133.82 | 65.75 | 4138.42 | 7.92 | 15.57 | Exact output and recorded work versus paired control |
| 32768-mtp-repeat-grid32-overlap0 | 32,768 | 1,024 | MTP | editing | 115.99 | 61.70 | 4220.72 | 7.76 | 16.59 | Exact output and recorded work versus paired control |
| 32768-mtp-repeat-grid384-overlap0 | 32,768 | 1,024 | MTP | coding | 132.52 | 65.47 | 4143.44 | 7.91 | 15.64 | Exact output and recorded work versus paired control |
| 32768-mtp-repeat-grid384-overlap0 | 32,768 | 1,024 | MTP | editing | 113.46 | 61.01 | 4225.40 | 7.75 | 16.78 | Exact output and recorded work versus paired control |
| 131072-mtp-grid384-overlap0 | 131,072 | 1,024 | MTP | coding | 133.72 | 25.72 | 4077.51 | 32.15 | 39.80 | Reference / no paired check in this record |
| 131072-mtp-grid384-overlap0 | 131,072 | 1,024 | MTP | editing | 107.75 | 24.62 | 4087.47 | 32.07 | 41.57 | Reference / no paired check in this record |
| 131072-mtp-grid32-overlap0 | 131,072 | 1,024 | MTP | coding | 134.91 | 25.77 | 4078.83 | 32.13 | 39.72 | Exact output and recorded work versus paired control |
| 131072-mtp-grid32-overlap0 | 131,072 | 1,024 | MTP | editing | 110.09 | 24.74 | 4086.98 | 32.07 | 41.37 | Exact output and recorded work versus paired control |
| 131072-mtp-grid32-overlap1 | 131,072 | 1,024 | MTP | coding | 136.52 | 25.84 | 4081.41 | 32.11 | 39.62 | Exact output and recorded work versus paired control |
| 131072-mtp-grid32-overlap1 | 131,072 | 1,024 | MTP | editing | 112.38 | 24.85 | 4085.48 | 32.08 | 41.19 | Exact output and recorded work versus paired control |
| 32768-plain-grid384-overlap0 | 32,768 | 1,024 | Plain | coding | 74.23 | 47.23 | 4158.22 | 7.88 | 21.68 | Reference / no paired check in this record |
| 32768-plain-grid384-overlap0 | 32,768 | 1,024 | Plain | editing | 62.44 | 42.47 | 4251.00 | 7.71 | 24.11 | Reference / no paired check in this record |
| 32768-plain-grid32-overlap0 | 32,768 | 1,024 | Plain | coding | 74.51 | 47.39 | 4168.06 | 7.86 | 21.61 | Exact output and recorded work versus paired control |
| 32768-plain-grid32-overlap0 | 32,768 | 1,024 | Plain | editing | 62.92 | 42.66 | 4241.43 | 7.73 | 24.00 | Exact output and recorded work versus paired control |
| 32768-plain-grid32-overlap1 | 32,768 | 1,024 | Plain | coding | 74.60 | 46.48 | 3948.28 | 8.30 | 22.03 | Reference / no paired check in this record |
| 32768-plain-grid32-overlap1 | 32,768 | 1,024 | Plain | editing | 61.54 | 41.80 | 4173.10 | 7.85 | 24.49 | Reference / no paired check in this record |

## cache-followups-live.json rtxpro-q8-host-dram-decode-20261004-r2

**Diagnostic: timings are not comparable serving benchmarks.**

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-coding-serial-control | 32,768 | 1,024 | MTP | coding | 132.60 | 65.48 | 4142.71 | 7.91 | 15.63 | Reference / no paired check in this record |
| 32768-mtp-coding-GPU-profile-control | 32,768 | 1,024 | MTP | coding | 129.81 | 64.64 | 4122.80 | 7.95 | 15.84 | Exact output and recorded work versus paired control |
| 32768-mtp-coding-serial-UMC | 32,768 | 1,024 | MTP | coding | 129.69 | 64.72 | 4138.78 | 7.92 | 15.81 | Exact output and recorded work versus paired control |
| 32768-mtp-coding-overlap-UMC | 32,768 | 1,024 | MTP | coding | 130.35 | 64.91 | 4141.03 | 7.91 | 15.77 | Exact output and recorded work versus paired control |
| 32768-mtp-editing-serial-control | 32,768 | 1,024 | MTP | editing | 93.06 | 54.08 | 4134.24 | 7.93 | 18.93 | Reference / no paired check in this record |
| 32768-mtp-editing-serial-UMC | 32,768 | 1,024 | MTP | editing | 91.64 | 53.63 | 4142.60 | 7.91 | 19.08 | Exact output and recorded work versus paired control |
| 32768-mtp-editing-overlap-UMC | 32,768 | 1,024 | MTP | editing | 93.26 | 54.15 | 4135.18 | 7.92 | 18.90 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-miss-geometry-32768-guarded-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-plain-grid384-overlap0 | 32,768 | 1,024 | Plain | coding | 74.21 | 47.24 | 4161.86 | 7.87 | 21.67 | Reference / no paired check in this record |
| 32768-plain-grid384-overlap0 | 32,768 | 1,024 | Plain | editing | 62.38 | 42.42 | 4244.67 | 7.72 | 24.13 | Reference / no paired check in this record |
| 32768-plain-grid32-overlap0 | 32,768 | 1,024 | Plain | coding | 74.47 | 47.32 | 4154.79 | 7.89 | 21.64 | Exact output and recorded work versus paired control |
| 32768-plain-grid32-overlap0 | 32,768 | 1,024 | Plain | editing | 62.81 | 42.62 | 4243.41 | 7.72 | 24.02 | Exact output and recorded work versus paired control |
| 32768-plain-grid32-overlap1 | 32,768 | 1,024 | Plain | coding | 74.66 | 47.40 | 4157.80 | 7.88 | 21.60 | Exact output and recorded work versus paired control |
| 32768-plain-grid32-overlap1 | 32,768 | 1,024 | Plain | editing | 63.22 | 42.84 | 4256.52 | 7.70 | 23.90 | Exact output and recorded work versus paired control |
| 32768-ngram-grid384-overlap0 | 32,768 | 1,024 | Plain+ngram | coding | 78.76 | 49.02 | 4155.79 | 7.88 | 20.89 | Reference / no paired check in this record |
| 32768-ngram-grid384-overlap0 | 32,768 | 1,024 | Plain+ngram | editing | 107.04 | 59.12 | 4229.60 | 7.75 | 17.31 | Reference / no paired check in this record |
| 32768-ngram-grid32-overlap0 | 32,768 | 1,024 | Plain+ngram | coding | 79.18 | 49.21 | 4163.50 | 7.87 | 20.80 | * Matching output; speculative work differs |
| 32768-ngram-grid32-overlap0 | 32,768 | 1,024 | Plain+ngram | editing | 115.37 | 61.63 | 4236.22 | 7.74 | 16.61 | * Matching output; speculative work differs |
| 32768-ngram-grid32-overlap1 | 32,768 | 1,024 | Plain+ngram | coding | 75.80 | 47.84 | 4153.32 | 7.89 | 21.40 | * First output difference at token 316; work may differ |
| 32768-ngram-grid32-overlap1 | 32,768 | 1,024 | Plain+ngram | editing | 118.53 | 62.56 | 4241.92 | 7.72 | 16.36 | * Matching output; speculative work differs |
| 32768-mtp-ngram-grid384-overlap0 | 32,768 | 1,024 | MTP+ngram | coding | 131.85 | 65.26 | 4137.84 | 7.92 | 15.69 | Reference / no paired check in this record |
| 32768-mtp-ngram-grid384-overlap0 | 32,768 | 1,024 | MTP+ngram | editing | 111.48 | 60.43 | 4225.08 | 7.76 | 16.94 | Reference / no paired check in this record |
| 32768-mtp-ngram-grid32-overlap0 | 32,768 | 1,024 | MTP+ngram | coding | 132.90 | 65.54 | 4141.09 | 7.91 | 15.62 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-grid32-overlap0 | 32,768 | 1,024 | MTP+ngram | editing | 114.62 | 61.35 | 4226.60 | 7.75 | 16.69 | * Matching output; speculative work differs |
| 32768-mtp-ngram-grid32-overlap1 | 32,768 | 1,024 | MTP+ngram | coding | 135.90 | 66.25 | 4138.89 | 7.92 | 15.45 | * First output difference at token 122; work may differ |
| 32768-mtp-ngram-grid32-overlap1 | 32,768 | 1,024 | MTP+ngram | editing | 120.21 | 62.86 | 4219.36 | 7.77 | 16.28 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-miss-geometry-131072-guarded-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 131072-plain-grid384-overlap0 | 131,072 | 1,024 | Plain | coding | 75.31 | 22.41 | 4084.46 | 32.09 | 45.69 | Reference / no paired check in this record |
| 131072-plain-grid384-overlap0 | 131,072 | 1,024 | Plain | editing | 60.38 | 20.89 | 4090.87 | 32.04 | 49.00 | Reference / no paired check in this record |
| 131072-plain-grid32-overlap0 | 131,072 | 1,024 | Plain | coding | 75.48 | 22.42 | 4083.46 | 32.10 | 45.67 | Exact output and recorded work versus paired control |
| 131072-plain-grid32-overlap0 | 131,072 | 1,024 | Plain | editing | 60.78 | 20.95 | 4093.20 | 32.02 | 48.87 | Exact output and recorded work versus paired control |
| 131072-plain-grid32-overlap1 | 131,072 | 1,024 | Plain | coding | 75.71 | 22.43 | 4081.69 | 32.11 | 45.64 | Exact output and recorded work versus paired control |
| 131072-plain-grid32-overlap1 | 131,072 | 1,024 | Plain | editing | 61.14 | 20.98 | 4089.62 | 32.05 | 48.80 | Exact output and recorded work versus paired control |
| 131072-ngram-grid384-overlap0 | 131,072 | 1,024 | Plain+ngram | coding | 76.42 | 22.50 | 4083.58 | 32.10 | 45.50 | Reference / no paired check in this record |
| 131072-ngram-grid384-overlap0 | 131,072 | 1,024 | Plain+ngram | editing | 102.68 | 24.37 | 4091.59 | 32.03 | 42.01 | Reference / no paired check in this record |
| 131072-ngram-grid32-overlap0 | 131,072 | 1,024 | Plain+ngram | coding | 75.81 | 22.44 | 4082.24 | 32.11 | 45.61 | * First output difference at token 580; work may differ |
| 131072-ngram-grid32-overlap0 | 131,072 | 1,024 | Plain+ngram | editing | 105.21 | 24.51 | 4092.66 | 32.03 | 41.76 | * Matching output; speculative work differs |
| 131072-ngram-grid32-overlap1 | 131,072 | 1,024 | Plain+ngram | coding | 75.18 | 22.38 | 4080.75 | 32.12 | 45.74 | * First output difference at token 308; work may differ |
| 131072-ngram-grid32-overlap1 | 131,072 | 1,024 | Plain+ngram | editing | 104.63 | 24.51 | 4098.95 | 31.98 | 41.76 | * Matching output; speculative work differs |
| 131072-mtp-ngram-grid384-overlap0 | 131,072 | 1,024 | MTP+ngram | coding | 133.53 | 25.72 | 4078.93 | 32.13 | 39.80 | Reference / no paired check in this record |
| 131072-mtp-ngram-grid384-overlap0 | 131,072 | 1,024 | MTP+ngram | editing | 106.80 | 24.56 | 4085.00 | 32.09 | 41.67 | Reference / no paired check in this record |
| 131072-mtp-ngram-grid32-overlap0 | 131,072 | 1,024 | MTP+ngram | coding | 134.64 | 25.77 | 4082.21 | 32.11 | 39.71 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-grid32-overlap0 | 131,072 | 1,024 | MTP+ngram | editing | 111.30 | 24.80 | 4087.72 | 32.06 | 41.27 | * Matching output; speculative work differs |
| 131072-mtp-ngram-grid32-overlap1 | 131,072 | 1,024 | MTP+ngram | coding | 135.81 | 25.78 | 4074.49 | 32.17 | 39.71 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-grid32-overlap1 | 131,072 | 1,024 | MTP+ngram | editing | 113.13 | 24.89 | 4087.49 | 32.07 | 41.12 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-cache-capacity-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-grid32-overlap1-ways4 | 32,768 | 1,024 | MTP | coding | 135.45 | 66.15 | 4139.62 | 7.92 | 15.48 | Reference / no paired check in this record |
| 32768-mtp-grid32-overlap1-ways4 | 32,768 | 1,024 | MTP | editing | 118.23 | 62.34 | 4222.03 | 7.76 | 16.42 | Reference / no paired check in this record |
| 32768-mtp-grid32-overlap1-ways8 | 32,768 | 1,024 | MTP | coding | 136.32 | 66.27 | 4129.60 | 7.93 | 15.45 | Exact output and recorded work versus paired control |
| 32768-mtp-grid32-overlap1-ways8 | 32,768 | 1,024 | MTP | editing | 119.73 | 62.75 | 4222.35 | 7.76 | 16.31 | Exact output and recorded work versus paired control |
| 32768-mtp-grid32-overlap1-ways16 | 32,768 | 1,024 | MTP | coding | 137.72 | 66.75 | 4147.43 | 7.90 | 15.34 | Exact output and recorded work versus paired control |
| 32768-mtp-grid32-overlap1-ways16 | 32,768 | 1,024 | MTP | editing | 122.93 | 63.63 | 4223.61 | 7.76 | 16.09 | Exact output and recorded work versus paired control |
| 32768-plain-grid32-overlap1-ways4 | 32,768 | 1,024 | Plain | coding | 74.72 | 47.41 | 4153.79 | 7.89 | 21.59 | Reference / no paired check in this record |
| 32768-plain-grid32-overlap1-ways4 | 32,768 | 1,024 | Plain | editing | 63.16 | 42.79 | 4248.91 | 7.71 | 23.92 | Reference / no paired check in this record |
| 32768-plain-grid32-overlap1-ways16 | 32,768 | 1,024 | Plain | coding | 75.50 | 47.75 | 4158.64 | 7.88 | 21.44 | Exact output and recorded work versus paired control |
| 32768-plain-grid32-overlap1-ways16 | 32,768 | 1,024 | Plain | editing | 64.84 | 43.54 | 4243.74 | 7.72 | 23.51 | Exact output and recorded work versus paired control |
| 32768-ngram-grid32-overlap1-ways4 | 32,768 | 1,024 | Plain+ngram | coding | 79.85 | 49.44 | 4156.37 | 7.88 | 20.71 | Reference / no paired check in this record |
| 32768-ngram-grid32-overlap1-ways4 | 32,768 | 1,024 | Plain+ngram | editing | 110.65 | 60.32 | 4246.26 | 7.72 | 16.97 | Reference / no paired check in this record |
| 32768-ngram-grid32-overlap1-ways16 | 32,768 | 1,024 | Plain+ngram | coding | 78.05 | 48.74 | 4155.21 | 7.89 | 21.01 | * First output difference at token 288; work may differ |
| 32768-ngram-grid32-overlap1-ways16 | 32,768 | 1,024 | Plain+ngram | editing | 121.35 | 63.30 | 4236.88 | 7.73 | 16.17 | * Matching output; speculative work differs |
| 32768-mtp-ngram-grid32-overlap1-ways4 | 32,768 | 1,024 | MTP+ngram | coding | 136.01 | 66.26 | 4137.01 | 7.92 | 15.45 | Reference / no paired check in this record |
| 32768-mtp-ngram-grid32-overlap1-ways4 | 32,768 | 1,024 | MTP+ngram | editing | 120.79 | 63.02 | 4218.93 | 7.77 | 16.24 | Reference / no paired check in this record |
| 32768-mtp-ngram-grid32-overlap1-ways16 | 32,768 | 1,024 | MTP+ngram | coding | 136.81 | 66.45 | 4136.75 | 7.92 | 15.41 | * First output difference at token 311; work may differ |
| 32768-mtp-ngram-grid32-overlap1-ways16 | 32,768 | 1,024 | MTP+ngram | editing | 121.42 | 63.18 | 4218.06 | 7.77 | 16.20 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-compact-fill-20261004-r3

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-compact0-grid32-ways4 | 32,768 | 1,024 | MTP | coding | 133.52 | 65.70 | 4141.45 | 7.91 | 15.58 | Exact output and recorded work versus paired control |
| 32768-mtp-compact0-grid32-ways4 | 32,768 | 1,024 | MTP | editing | 118.33 | 62.38 | 4224.04 | 7.76 | 16.41 | Exact output and recorded work versus paired control |
| 32768-mtp-compact1-grid32-ways4 | 32,768 | 1,024 | MTP | coding | 135.39 | 66.12 | 4137.74 | 7.92 | 15.48 | Exact output and recorded work versus paired control |
| 32768-mtp-compact1-grid32-ways4 | 32,768 | 1,024 | MTP | editing | 118.15 | 62.33 | 4223.77 | 7.76 | 16.42 | Exact output and recorded work versus paired control |
| 32768-plain-compact0-grid32-ways4 | 32,768 | 1,024 | Plain | coding | 74.60 | 47.35 | 4151.16 | 7.89 | 21.62 | Exact output and recorded work versus paired control |
| 32768-plain-compact0-grid32-ways4 | 32,768 | 1,024 | Plain | editing | 63.09 | 42.75 | 4244.17 | 7.72 | 23.95 | Exact output and recorded work versus paired control |
| 32768-plain-compact1-grid32-ways4 | 32,768 | 1,024 | Plain | coding | 74.70 | 47.42 | 4157.48 | 7.88 | 21.59 | Exact output and recorded work versus paired control |
| 32768-plain-compact1-grid32-ways4 | 32,768 | 1,024 | Plain | editing | 63.12 | 42.76 | 4244.45 | 7.72 | 23.94 | Exact output and recorded work versus paired control |
| 32768-ngram-compact0-grid32-ways4 | 32,768 | 1,024 | Plain+ngram | coding | 78.82 | 49.07 | 4162.39 | 7.87 | 20.86 | * First output difference at token 316; work may differ |
| 32768-ngram-compact0-grid32-ways4 | 32,768 | 1,024 | Plain+ngram | editing | 111.33 | 60.49 | 4242.03 | 7.72 | 16.92 | * Matching output; speculative work differs |
| 32768-ngram-compact1-grid32-ways4 | 32,768 | 1,024 | Plain+ngram | coding | 79.63 | 49.36 | 4157.80 | 7.88 | 20.74 | * Matching output; speculative work differs |
| 32768-ngram-compact1-grid32-ways4 | 32,768 | 1,024 | Plain+ngram | editing | 113.03 | 60.98 | 4240.17 | 7.73 | 16.79 | * Matching output; speculative work differs |
| 32768-mtp-ngram-compact0-grid32-ways4 | 32,768 | 1,024 | MTP+ngram | coding | 134.36 | 65.89 | 4140.46 | 7.91 | 15.54 | * First output difference at token 311; work may differ |
| 32768-mtp-ngram-compact0-grid32-ways4 | 32,768 | 1,024 | MTP+ngram | editing | 116.69 | 61.86 | 4215.40 | 7.77 | 16.55 | * Matching output; speculative work differs |
| 32768-mtp-ngram-compact1-grid32-ways4 | 32,768 | 1,024 | MTP+ngram | coding | 136.05 | 66.29 | 4138.94 | 7.92 | 15.44 | * First output difference at token 311; work may differ |
| 32768-mtp-ngram-compact1-grid32-ways4 | 32,768 | 1,024 | MTP+ngram | editing | 116.78 | 61.91 | 4219.58 | 7.77 | 16.53 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-compact-followup-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-compact1-reverse | 32,768 | 1,024 | MTP | coding | 134.80 | 65.84 | 4121.19 | 7.95 | 15.55 | Exact output and recorded work versus paired control |
| 32768-mtp-compact1-reverse | 32,768 | 1,024 | MTP | editing | 118.43 | 62.41 | 4224.53 | 7.76 | 16.40 | Exact output and recorded work versus paired control |
| 32768-mtp-compact0-reverse | 32,768 | 1,024 | MTP | coding | 135.04 | 66.01 | 4134.92 | 7.92 | 15.51 | Exact output and recorded work versus paired control |
| 32768-mtp-compact0-reverse | 32,768 | 1,024 | MTP | editing | 118.16 | 62.32 | 4222.03 | 7.76 | 16.43 | Exact output and recorded work versus paired control |
| 131072-mtp-compact0 | 131,072 | 1,024 | MTP | coding | 136.62 | 25.85 | 4082.58 | 32.11 | 39.60 | Reference / no paired check in this record |
| 131072-mtp-compact0 | 131,072 | 1,024 | MTP | editing | 112.44 | 24.86 | 4087.21 | 32.07 | 41.18 | Reference / no paired check in this record |
| 131072-mtp-compact1 | 131,072 | 1,024 | MTP | coding | 136.11 | 25.81 | 4078.75 | 32.14 | 39.66 | Exact output and recorded work versus paired control |
| 131072-mtp-compact1 | 131,072 | 1,024 | MTP | editing | 112.41 | 24.85 | 4085.54 | 32.08 | 41.19 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-layer-admission-20261004-r2

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-admission-control | 32,768 | 1,024 | MTP | coding | 135.01 | 66.00 | 4134.55 | 7.93 | 15.51 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-control | 32,768 | 1,024 | MTP | editing | 119.00 | 62.55 | 4221.81 | 7.76 | 16.37 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-deferred | 32,768 | 1,024 | MTP | coding | 136.36 | 66.34 | 4137.01 | 7.92 | 15.43 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-deferred | 32,768 | 1,024 | MTP | editing | 119.56 | 62.65 | 4213.50 | 7.78 | 16.34 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-layer | 32,768 | 1,024 | MTP | coding | 144.56 | 68.27 | 4141.77 | 7.91 | 15.00 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-layer | 32,768 | 1,024 | MTP | editing | 124.43 | 64.02 | 4221.48 | 7.76 | 15.99 | Exact output and recorded work versus paired control |
| 32768-plain-admission-control | 32,768 | 1,024 | Plain | coding | 75.19 | 47.67 | 4168.53 | 7.86 | 21.48 | Exact output and recorded work versus paired control |
| 32768-plain-admission-control | 32,768 | 1,024 | Plain | editing | 63.78 | 43.06 | 4244.17 | 7.72 | 23.77 | Exact output and recorded work versus paired control |
| 32768-plain-admission-layer | 32,768 | 1,024 | Plain | coding | 77.52 | 48.54 | 4157.16 | 7.88 | 21.09 | Exact output and recorded work versus paired control |
| 32768-plain-admission-layer | 32,768 | 1,024 | Plain | editing | 65.54 | 43.85 | 4243.08 | 7.72 | 23.35 | Exact output and recorded work versus paired control |
| 32768-ngram-admission-control | 32,768 | 1,024 | Plain+ngram | coding | 80.43 | 49.67 | 4158.90 | 7.88 | 20.61 | * First output difference at token 316; work may differ |
| 32768-ngram-admission-control | 32,768 | 1,024 | Plain+ngram | editing | 115.60 | 61.76 | 4246.26 | 7.72 | 16.58 | * Matching output; speculative work differs |
| 32768-ngram-admission-layer | 32,768 | 1,024 | Plain+ngram | coding | 78.87 | 49.06 | 4156.21 | 7.88 | 20.87 | * First output difference at token 120; work may differ |
| 32768-ngram-admission-layer | 32,768 | 1,024 | Plain+ngram | editing | 108.65 | 59.72 | 4245.27 | 7.72 | 17.14 | * Matching output; speculative work differs |
| 32768-mtp-ngram-admission-control | 32,768 | 1,024 | MTP+ngram | coding | 136.94 | 66.51 | 4140.62 | 7.91 | 15.39 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-admission-control | 32,768 | 1,024 | MTP+ngram | editing | 120.73 | 63.04 | 4224.59 | 7.76 | 16.24 | * Matching output; speculative work differs |
| 32768-mtp-ngram-admission-layer | 32,768 | 1,024 | MTP+ngram | coding | 143.82 | 68.17 | 4149.16 | 7.90 | 15.02 | * First output difference at token 311; work may differ |
| 32768-mtp-ngram-admission-layer | 32,768 | 1,024 | MTP+ngram | editing | 122.80 | 63.56 | 4218.98 | 7.77 | 16.11 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-cache-budget-20261004-r2

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-primary15472-ways16 | 32,768 | 1,024 | MTP | coding | 137.51 | 66.55 | 4129.08 | 7.94 | 15.38 | Exact output and recorded work versus paired control |
| 32768-mtp-primary15472-ways16 | 32,768 | 1,024 | MTP | editing | 123.36 | 63.75 | 4224.69 | 7.76 | 16.06 | Exact output and recorded work versus paired control |
| 32768-mtp-primary16048-ways4 | 32,768 | 1,024 | MTP | coding | 139.16 | 68.94 | 4374.14 | 7.49 | 14.85 | * First output difference at token 120; work may differ |
| 32768-mtp-primary16048-ways4 | 32,768 | 1,024 | MTP | editing | 121.50 | 64.88 | 4457.75 | 7.35 | 15.78 | * Matching output; speculative work differs |
| 32768-mtp-primary15472-ways4 | 32,768 | 1,024 | MTP | coding | 135.38 | 66.13 | 4139.78 | 7.92 | 15.48 | Exact output and recorded work versus paired control |
| 32768-mtp-primary15472-ways4 | 32,768 | 1,024 | MTP | editing | 118.23 | 62.35 | 4223.55 | 7.76 | 16.42 | Exact output and recorded work versus paired control |
| 32768-plain-primary15472-ways16 | 32,768 | 1,024 | Plain | coding | 75.50 | 47.75 | 4158.06 | 7.88 | 21.44 | Exact output and recorded work versus paired control |
| 32768-plain-primary15472-ways16 | 32,768 | 1,024 | Plain | editing | 64.71 | 43.48 | 4244.12 | 7.72 | 23.54 | Exact output and recorded work versus paired control |
| 32768-plain-primary15472-ways4 | 32,768 | 1,024 | Plain | coding | 74.61 | 47.33 | 4145.28 | 7.90 | 21.63 | Exact output and recorded work versus paired control |
| 32768-plain-primary15472-ways4 | 32,768 | 1,024 | Plain | editing | 63.22 | 42.81 | 4245.99 | 7.72 | 23.91 | Exact output and recorded work versus paired control |
| 131072-mtp-primary15472-ways4 | 131,072 | 1,024 | MTP | coding | 136.49 | 25.82 | 4077.02 | 32.15 | 39.65 | Reference / no paired check in this record |
| 131072-mtp-primary15472-ways4 | 131,072 | 1,024 | MTP | editing | 112.74 | 24.86 | 4084.92 | 32.09 | 41.17 | Reference / no paired check in this record |
| 131072-mtp-primary15472-ways16 | 131,072 | 1,024 | MTP | coding | 138.43 | 25.89 | 4078.18 | 32.14 | 39.54 | Exact output and recorded work versus paired control |
| 131072-mtp-primary15472-ways16 | 131,072 | 1,024 | MTP | editing | 116.35 | 25.03 | 4085.26 | 32.08 | 40.89 | Exact output and recorded work versus paired control |
| 131072-mtp-primary16048-ways4 | 131,072 | 1,024 | MTP | coding | 138.92 | 27.03 | 4298.05 | 30.50 | 37.87 | * First output difference at token 32; work may differ |
| 131072-mtp-primary16048-ways4 | 131,072 | 1,024 | MTP | editing | 117.71 | 26.23 | 4321.83 | 30.33 | 39.03 | * Matching output; speculative work differs |
| 131072-plain-primary15472-ways4 | 131,072 | 1,024 | Plain | coding | 75.39 | 22.40 | 4080.75 | 32.12 | 45.70 | Reference / no paired check in this record |
| 131072-plain-primary15472-ways4 | 131,072 | 1,024 | Plain | editing | 61.05 | 20.96 | 4088.07 | 32.06 | 48.84 | Reference / no paired check in this record |
| 131072-plain-primary15472-ways16 | 131,072 | 1,024 | Plain | coding | 76.19 | 22.49 | 4085.68 | 32.08 | 45.52 | Exact output and recorded work versus paired control |
| 131072-plain-primary15472-ways16 | 131,072 | 1,024 | Plain | editing | 62.26 | 21.11 | 4089.58 | 32.05 | 48.50 | Exact output and recorded work versus paired control |
| 131072-ngram-primary15472-ways4 | 131,072 | 1,024 | Plain+ngram | coding | 75.55 | 22.41 | 4081.04 | 32.12 | 45.67 | Reference / no paired check in this record |
| 131072-ngram-primary15472-ways4 | 131,072 | 1,024 | Plain+ngram | editing | 108.09 | 24.70 | 4100.69 | 31.96 | 41.44 | Reference / no paired check in this record |
| 131072-ngram-primary15472-ways16 | 131,072 | 1,024 | Plain+ngram | coding | 76.07 | 22.47 | 4083.32 | 32.10 | 45.56 | Exact output and recorded work versus paired control |
| 131072-ngram-primary15472-ways16 | 131,072 | 1,024 | Plain+ngram | editing | 111.15 | 24.86 | 4101.27 | 31.96 | 41.17 | * Matching output; speculative work differs |
| 131072-mtp-ngram-primary15472-ways4 | 131,072 | 1,024 | MTP+ngram | coding | 136.17 | 25.79 | 4075.22 | 32.16 | 39.68 | Reference / no paired check in this record |
| 131072-mtp-ngram-primary15472-ways4 | 131,072 | 1,024 | MTP+ngram | editing | 111.79 | 24.81 | 4083.38 | 32.10 | 41.26 | Reference / no paired check in this record |
| 131072-mtp-ngram-primary15472-ways16 | 131,072 | 1,024 | MTP+ngram | coding | 137.74 | 25.86 | 4077.56 | 32.14 | 39.58 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-primary15472-ways16 | 131,072 | 1,024 | MTP+ngram | editing | 117.81 | 25.10 | 4085.87 | 32.08 | 40.77 | * Matching output; speculative work differs |
| 32768-mtp-primary16560-ways4 | 32,768 | 1,024 | MTP | coding | 145.68 | 72.39 | 4607.81 | 7.11 | 14.14 | * First output difference at token 120; work may differ |
| 32768-mtp-primary16560-ways4 | 32,768 | 1,024 | MTP | editing | 127.46 | 68.24 | 4703.86 | 6.97 | 15.00 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-cache-routing-20261004-r2

**Diagnostic: timings are not comparable serving benchmarks.**

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-plain-cache-routing16 | 32,768 | 1,024 | Plain | coding | 74.91 | 47.51 | 4159.59 | 7.88 | 21.55 | Exact output and recorded work versus paired control |
| 32768-plain-cache-routing16 | 32,768 | 1,024 | Plain | editing | 63.90 | 43.12 | 4246.26 | 7.72 | 23.74 | Exact output and recorded work versus paired control |
| 32768-mtp-cache-routing16 | 32,768 | 1,024 | MTP | coding | 135.82 | 66.22 | 4137.84 | 7.92 | 15.46 | Exact output and recorded work versus paired control |
| 32768-mtp-cache-routing16 | 32,768 | 1,024 | MTP | editing | 122.75 | 63.58 | 4223.50 | 7.76 | 16.10 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-gpu-refills-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-gpu-control | 32,768 | 1,024 | MTP | coding | 138.31 | 66.80 | 4136.54 | 7.92 | 15.32 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-control | 32,768 | 1,024 | MTP | editing | 124.46 | 64.04 | 4224.42 | 7.76 | 15.98 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-snapshot | 32,768 | 1,024 | MTP | coding | 138.61 | 66.84 | 4133.09 | 7.93 | 15.32 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-snapshot | 32,768 | 1,024 | MTP | editing | 124.66 | 64.03 | 4214.70 | 7.77 | 15.99 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-refill | 32,768 | 1,024 | MTP | coding | 140.58 | 67.36 | 4140.82 | 7.91 | 15.20 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-refill | 32,768 | 1,024 | MTP | editing | 126.32 | 64.52 | 4222.35 | 7.76 | 15.87 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-control | 32,768 | 1,024 | Plain | coding | 76.22 | 48.03 | 4158.90 | 7.88 | 21.31 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-control | 32,768 | 1,024 | Plain | editing | 65.85 | 44.01 | 4247.31 | 7.71 | 23.27 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-snapshot | 32,768 | 1,024 | Plain | coding | 76.18 | 48.01 | 4157.00 | 7.88 | 21.32 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-snapshot | 32,768 | 1,024 | Plain | editing | 65.90 | 44.02 | 4245.77 | 7.72 | 23.26 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-refill | 32,768 | 1,024 | Plain | coding | 76.78 | 48.15 | 4134.45 | 7.93 | 21.26 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-refill | 32,768 | 1,024 | Plain | editing | 66.19 | 44.15 | 4244.39 | 7.72 | 23.19 | Exact output and recorded work versus paired control |
| 32768-ngram-gpu-control | 32,768 | 1,024 | Plain+ngram | coding | 80.88 | 49.91 | 4173.04 | 7.85 | 20.51 | Reference / no paired check in this record |
| 32768-ngram-gpu-control | 32,768 | 1,024 | Plain+ngram | editing | 121.57 | 63.37 | 4238.25 | 7.73 | 16.15 | Reference / no paired check in this record |
| 32768-ngram-gpu-refill | 32,768 | 1,024 | Plain+ngram | coding | 79.31 | 49.26 | 4162.60 | 7.87 | 20.78 | * First output difference at token 288; work may differ |
| 32768-ngram-gpu-refill | 32,768 | 1,024 | Plain+ngram | editing | 121.47 | 63.36 | 4241.37 | 7.73 | 16.16 | * Matching output; speculative work differs |
| 32768-mtp-ngram-gpu-control | 32,768 | 1,024 | MTP+ngram | coding | 137.85 | 66.79 | 4148.16 | 7.90 | 15.33 | Reference / no paired check in this record |
| 32768-mtp-ngram-gpu-control | 32,768 | 1,024 | MTP+ngram | editing | 121.96 | 63.33 | 4218.22 | 7.77 | 16.16 | Reference / no paired check in this record |
| 32768-mtp-ngram-gpu-refill | 32,768 | 1,024 | MTP+ngram | coding | 139.67 | 67.11 | 4136.07 | 7.92 | 15.25 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-gpu-refill | 32,768 | 1,024 | MTP+ngram | editing | 123.80 | 63.81 | 4216.70 | 7.77 | 16.04 | Exact output and recorded work versus paired control |

## cache-followups-live.json rtxpro-q8-layer-followup-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-admission-layer-reverse | 32,768 | 1,024 | MTP | coding | 144.43 | 67.83 | 4095.33 | 8.00 | 15.09 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-layer-reverse | 32,768 | 1,024 | MTP | editing | 124.36 | 64.01 | 4223.12 | 7.76 | 15.99 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-control-reverse | 32,768 | 1,024 | MTP | coding | 136.42 | 66.37 | 4138.84 | 7.92 | 15.42 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-control-reverse | 32,768 | 1,024 | MTP | editing | 119.30 | 62.64 | 4222.14 | 7.76 | 16.34 | Exact output and recorded work versus paired control |
| 131072-mtp-admission-control | 131,072 | 1,024 | MTP | coding | 137.64 | 25.86 | 4078.26 | 32.14 | 39.58 | Reference / no paired check in this record |
| 131072-mtp-admission-control | 131,072 | 1,024 | MTP | editing | 113.66 | 24.92 | 4087.57 | 32.07 | 41.08 | Reference / no paired check in this record |
| 131072-mtp-admission-layer | 131,072 | 1,024 | MTP | coding | 145.06 | 26.10 | 4076.09 | 32.16 | 39.22 | Exact output and recorded work versus paired control |
| 131072-mtp-admission-layer | 131,072 | 1,024 | MTP | editing | 118.45 | 25.14 | 4086.50 | 32.07 | 40.72 | Exact output and recorded work versus paired control |
| 131072-plain-admission-control | 131,072 | 1,024 | Plain | coding | 76.33 | 22.49 | 4081.97 | 32.11 | 45.53 | Reference / no paired check in this record |
| 131072-plain-admission-control | 131,072 | 1,024 | Plain | editing | 61.91 | 21.08 | 4094.55 | 32.01 | 48.55 | Reference / no paired check in this record |
| 131072-plain-admission-layer | 131,072 | 1,024 | Plain | coding | 78.21 | 22.66 | 4085.12 | 32.09 | 45.18 | Exact output and recorded work versus paired control |
| 131072-plain-admission-layer | 131,072 | 1,024 | Plain | editing | 63.46 | 21.25 | 4091.51 | 32.04 | 48.17 | Exact output and recorded work versus paired control |
| 131072-ngram-admission-control | 131,072 | 1,024 | Plain+ngram | coding | 76.89 | 22.53 | 4082.65 | 32.10 | 45.42 | Reference / no paired check in this record |
| 131072-ngram-admission-control | 131,072 | 1,024 | Plain+ngram | editing | 110.77 | 24.86 | 4104.44 | 31.93 | 41.18 | Reference / no paired check in this record |
| 131072-ngram-admission-layer | 131,072 | 1,024 | Plain+ngram | coding | 78.20 | 22.66 | 4084.95 | 32.09 | 45.18 | * First output difference at token 221; work may differ |
| 131072-ngram-admission-layer | 131,072 | 1,024 | Plain+ngram | editing | 113.53 | 24.94 | 4092.82 | 32.02 | 41.04 | * Matching output; speculative work differs |
| 131072-mtp-ngram-admission-control | 131,072 | 1,024 | MTP+ngram | coding | 136.93 | 25.82 | 4076.32 | 32.15 | 39.63 | Reference / no paired check in this record |
| 131072-mtp-ngram-admission-control | 131,072 | 1,024 | MTP+ngram | editing | 111.40 | 24.81 | 4088.69 | 32.06 | 41.25 | Reference / no paired check in this record |
| 131072-mtp-ngram-admission-layer | 131,072 | 1,024 | MTP+ngram | coding | 144.30 | 26.08 | 4077.31 | 32.15 | 39.24 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-admission-layer | 131,072 | 1,024 | MTP+ngram | editing | 118.61 | 25.16 | 4090.39 | 32.04 | 40.68 | * Matching output; speculative work differs |

## cache-followups-live.json rtxpro-q8-gpu-refill-followup-20261004

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-gpu-refill-reverse | 32,768 | 1,024 | MTP | coding | 140.69 | 67.39 | 4141.40 | 7.91 | 15.19 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-refill-reverse | 32,768 | 1,024 | MTP | editing | 126.27 | 64.53 | 4225.46 | 7.75 | 15.86 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-control-reverse | 32,768 | 1,024 | MTP | coding | 138.74 | 66.94 | 4141.77 | 7.91 | 15.29 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-control-reverse | 32,768 | 1,024 | MTP | editing | 124.56 | 64.07 | 4223.99 | 7.76 | 15.98 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-refill-reverse | 32,768 | 1,024 | Plain | coding | 76.83 | 48.32 | 4169.33 | 7.86 | 21.19 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-refill-reverse | 32,768 | 1,024 | Plain | editing | 66.34 | 44.22 | 4245.44 | 7.72 | 23.15 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-control-reverse | 32,768 | 1,024 | Plain | coding | 76.32 | 48.07 | 4156.63 | 7.88 | 21.30 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-control-reverse | 32,768 | 1,024 | Plain | editing | 65.82 | 43.98 | 4243.84 | 7.72 | 23.28 | Exact output and recorded work versus paired control |

## live.json jobs

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-plain-control | 32,768 | 1,024 | Plain | coding | 71.80 | 46.22 | 4157.27 | 7.88 | 22.14 | Reference / no paired check in this record |
| 32768-plain-control | 32,768 | 1,024 | Plain | editing | 60.51 | 41.57 | 4252.33 | 7.71 | 24.63 | Reference / no paired check in this record |
| 131072-plain-control | 131,072 | 1,024 | Plain | coding | 72.99 | 22.19 | 4081.60 | 32.11 | 46.14 | Reference / no paired check in this record |
| 131072-plain-control | 131,072 | 1,024 | Plain | editing | 58.29 | 20.64 | 4092.34 | 32.03 | 49.60 | Reference / no paired check in this record |
| 32768-mtp-control | 32,768 | 1,024 | MTP | coding | 122.20 | 62.65 | 4116.94 | 7.96 | 16.34 | Reference / no paired check in this record |
| 32768-mtp-control | 32,768 | 1,024 | MTP | editing | 105.54 | 58.63 | 4223.99 | 7.76 | 17.46 | Reference / no paired check in this record |
| 131072-mtp-control | 131,072 | 1,024 | MTP | coding | 124.78 | 25.36 | 4076.88 | 32.15 | 40.36 | Reference / no paired check in this record |
| 131072-mtp-control | 131,072 | 1,024 | MTP | editing | 100.12 | 24.18 | 4083.38 | 32.10 | 42.33 | Reference / no paired check in this record |
| 32768-ngram-control | 32,768 | 1,024 | Plain+ngram | coding | 74.62 | 47.36 | 4150.21 | 7.90 | 21.62 | Reference / no paired check in this record |
| 32768-ngram-control | 32,768 | 1,024 | Plain+ngram | editing | 103.84 | 58.16 | 4233.21 | 7.74 | 17.60 | Reference / no paired check in this record |
| 131072-ngram-control | 131,072 | 1,024 | Plain+ngram | coding | 73.35 | 22.21 | 4080.49 | 32.12 | 46.08 | Reference / no paired check in this record |
| 131072-ngram-control | 131,072 | 1,024 | Plain+ngram | editing | 90.67 | 23.65 | 4096.65 | 31.99 | 43.29 | Reference / no paired check in this record |
| 32768-mtp-ngram-control | 32,768 | 1,024 | MTP+ngram | coding | 121.53 | 62.50 | 4119.95 | 7.95 | 16.38 | Reference / no paired check in this record |
| 32768-mtp-ngram-control | 32,768 | 1,024 | MTP+ngram | editing | 102.97 | 57.88 | 4232.72 | 7.74 | 17.69 | Reference / no paired check in this record |
| 131072-mtp-ngram-control | 131,072 | 1,024 | MTP+ngram | coding | 124.49 | 25.32 | 4071.38 | 32.19 | 40.42 | Reference / no paired check in this record |
| 131072-mtp-ngram-control | 131,072 | 1,024 | MTP+ngram | editing | 99.16 | 24.14 | 4086.61 | 32.07 | 42.40 | Reference / no paired check in this record |
| 32768-plain-default-off | 32,768 | 1,024 | Plain | coding | 71.97 | 46.29 | 4153.89 | 7.89 | 22.12 | Exact output and recorded work versus paired control |
| 32768-plain-default-off | 32,768 | 1,024 | Plain | editing | 60.59 | 41.58 | 4244.39 | 7.72 | 24.62 | Exact output and recorded work versus paired control |
| 32768-mtp-default-off | 32,768 | 1,024 | MTP | coding | 122.36 | 62.71 | 4119.27 | 7.95 | 16.32 | Exact output and recorded work versus paired control |
| 32768-mtp-default-off | 32,768 | 1,024 | MTP | editing | 105.64 | 58.66 | 4222.35 | 7.76 | 17.45 | Exact output and recorded work versus paired control |
| 32768-plain-persistent | 32,768 | 1,024 | Plain | coding | 71.92 | 46.22 | 4140.82 | 7.91 | 22.15 | Exact output and recorded work versus paired control |
| 32768-plain-persistent | 32,768 | 1,024 | Plain | editing | 60.60 | 41.59 | 4246.26 | 7.72 | 24.61 | Exact output and recorded work versus paired control |
| 131072-plain-persistent | 131,072 | 1,024 | Plain | coding | 73.14 | 22.21 | 4085.19 | 32.08 | 46.09 | Exact output and recorded work versus paired control |
| 131072-plain-persistent | 131,072 | 1,024 | Plain | editing | 58.46 | 20.66 | 4092.50 | 32.03 | 49.54 | Exact output and recorded work versus paired control |
| 32768-mtp-persistent | 32,768 | 1,024 | MTP | coding | 122.14 | 62.65 | 4118.76 | 7.96 | 16.34 | Exact output and recorded work versus paired control |
| 32768-mtp-persistent | 32,768 | 1,024 | MTP | editing | 105.78 | 58.70 | 4222.30 | 7.76 | 17.44 | Exact output and recorded work versus paired control |
| 131072-mtp-persistent | 131,072 | 1,024 | MTP | coding | 124.94 | 25.36 | 4074.77 | 32.17 | 40.36 | Exact output and recorded work versus paired control |
| 131072-mtp-persistent | 131,072 | 1,024 | MTP | editing | 100.39 | 24.22 | 4089.48 | 32.05 | 42.25 | Exact output and recorded work versus paired control |
| 32768-ngram-persistent | 32,768 | 1,024 | Plain+ngram | coding | 73.79 | 47.07 | 4160.65 | 7.88 | 21.75 | * First output difference at token 120; work may differ |
| 32768-ngram-persistent | 32,768 | 1,024 | Plain+ngram | editing | 98.67 | 56.52 | 4236.99 | 7.73 | 18.11 | * Matching output; speculative work differs |
| 131072-ngram-persistent | 131,072 | 1,024 | Plain+ngram | coding | 73.35 | 22.22 | 4081.97 | 32.11 | 46.07 | * First output difference at token 606; work may differ |
| 131072-ngram-persistent | 131,072 | 1,024 | Plain+ngram | editing | 94.15 | 23.86 | 4093.61 | 32.02 | 42.89 | * Matching output; speculative work differs |
| 32768-mtp-ngram-persistent | 32,768 | 1,024 | MTP+ngram | coding | 121.49 | 62.44 | 4114.31 | 7.96 | 16.39 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-persistent | 32,768 | 1,024 | MTP+ngram | editing | 103.05 | 57.85 | 4223.71 | 7.76 | 17.70 | * Matching output; speculative work differs |
| 131072-mtp-ngram-persistent | 131,072 | 1,024 | MTP+ngram | coding | 125.05 | 25.39 | 4079.34 | 32.13 | 40.32 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-persistent | 131,072 | 1,024 | MTP+ngram | editing | 97.49 | 24.05 | 4088.28 | 32.06 | 42.56 | * Matching output; speculative work differs |
| 32768-plain-pool7 | 32,768 | 1,024 | Plain | coding | 71.79 | 46.24 | 4158.75 | 7.88 | 22.14 | Exact output and recorded work versus paired control |
| 32768-plain-pool7 | 32,768 | 1,024 | Plain | editing | 60.64 | 41.60 | 4243.95 | 7.72 | 24.61 | Exact output and recorded work versus paired control |
| 131072-plain-pool7 | 131,072 | 1,024 | Plain | coding | 71.33 | 22.03 | 4082.96 | 32.10 | 46.46 | Exact output and recorded work versus paired control |
| 131072-plain-pool7 | 131,072 | 1,024 | Plain | editing | 56.45 | 20.40 | 4090.94 | 32.04 | 50.18 | Exact output and recorded work versus paired control |
| 32768-mtp-pool7 | 32,768 | 1,024 | MTP | coding | 121.89 | 62.59 | 4119.17 | 7.96 | 16.36 | Exact output and recorded work versus paired control |
| 32768-mtp-pool7 | 32,768 | 1,024 | MTP | editing | 105.89 | 58.72 | 4221.16 | 7.76 | 17.43 | Exact output and recorded work versus paired control |
| 131072-mtp-pool7 | 131,072 | 1,024 | MTP | coding | 124.93 | 25.34 | 4070.36 | 32.20 | 40.40 | Exact output and recorded work versus paired control |
| 131072-mtp-pool7 | 131,072 | 1,024 | MTP | editing | 100.49 | 24.21 | 4083.57 | 32.10 | 42.29 | Exact output and recorded work versus paired control |
| 32768-plain-default-off | 32,768 | 1,024 | Plain | coding | 71.69 | 46.19 | 4158.16 | 7.88 | 22.16 | Exact output and recorded work versus paired control |
| 32768-plain-default-off | 32,768 | 1,024 | Plain | editing | 60.51 | 41.57 | 4252.27 | 7.71 | 24.63 | Exact output and recorded work versus paired control |
| 32768-mtp-default-off | 32,768 | 1,024 | MTP | coding | 121.95 | 62.77 | 4141.35 | 7.91 | 16.31 | Exact output and recorded work versus paired control |
| 32768-mtp-default-off | 32,768 | 1,024 | MTP | editing | 105.44 | 58.60 | 4224.26 | 7.76 | 17.47 | Exact output and recorded work versus paired control |
| 32768-plain-duplex | 32,768 | 1,024 | Plain | coding | 73.49 | 46.83 | 4134.03 | 7.93 | 21.86 | Exact output and recorded work versus paired control |
| 32768-plain-duplex | 32,768 | 1,024 | Plain | editing | 62.06 | 42.27 | 4244.17 | 7.72 | 24.22 | Exact output and recorded work versus paired control |
| 131072-plain-duplex | 131,072 | 1,024 | Plain | coding | 74.88 | 22.37 | 4084.92 | 32.09 | 45.76 | Exact output and recorded work versus paired control |
| 131072-plain-duplex | 131,072 | 1,024 | Plain | editing | 59.87 | 20.82 | 4088.73 | 32.06 | 49.16 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex | 32,768 | 1,024 | MTP | coding | 130.18 | 64.76 | 4125.55 | 7.94 | 15.81 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex | 32,768 | 1,024 | MTP | editing | 112.10 | 60.58 | 4220.72 | 7.76 | 16.90 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex | 131,072 | 1,024 | MTP | coding | 132.20 | 25.65 | 4075.90 | 32.16 | 39.90 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex | 131,072 | 1,024 | MTP | editing | 106.52 | 24.56 | 4088.10 | 32.06 | 41.67 | Exact output and recorded work versus paired control |
| 32768-ngram-duplex | 32,768 | 1,024 | Plain+ngram | coding | 75.15 | 47.51 | 4136.90 | 7.92 | 21.55 | * First output difference at token 268; work may differ |
| 32768-ngram-duplex | 32,768 | 1,024 | Plain+ngram | editing | 104.58 | 58.43 | 4239.34 | 7.73 | 17.52 | * Matching output; speculative work differs |
| 131072-ngram-duplex | 131,072 | 1,024 | Plain+ngram | coding | 75.15 | 22.38 | 4082.60 | 32.10 | 45.73 | * First output difference at token 331; work may differ |
| 131072-ngram-duplex | 131,072 | 1,024 | Plain+ngram | editing | 101.35 | 24.27 | 4086.66 | 32.07 | 42.18 | * Matching output; speculative work differs |
| 32768-mtp-ngram-duplex | 32,768 | 1,024 | MTP+ngram | coding | 128.76 | 64.57 | 4146.80 | 7.90 | 15.85 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-duplex | 32,768 | 1,024 | MTP+ngram | editing | 108.70 | 59.59 | 4223.77 | 7.76 | 17.18 | * Matching output; speculative work differs |
| 131072-mtp-ngram-duplex | 131,072 | 1,024 | MTP+ngram | coding | 131.43 | 25.63 | 4077.03 | 32.15 | 39.94 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-duplex | 131,072 | 1,024 | MTP+ngram | editing | 103.93 | 24.41 | 4087.09 | 32.07 | 41.92 | * Matching output; speculative work differs |
| 32768-mtp-worker-cpu16 | 32,768 | 1,024 | MTP | coding | 123.05 | 63.05 | 4140.30 | 7.91 | 16.24 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-cpu16 | 32,768 | 1,024 | MTP | editing | 106.04 | 58.77 | 4221.92 | 7.76 | 17.42 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-cpu0-after16 | 32,768 | 1,024 | MTP | coding | 122.09 | 62.77 | 4136.90 | 7.92 | 16.31 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-cpu0-after16 | 32,768 | 1,024 | MTP | editing | 105.82 | 58.72 | 4223.50 | 7.76 | 17.44 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-cpu24 | 32,768 | 1,024 | MTP | coding | 122.86 | 62.98 | 4137.48 | 7.92 | 16.25 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-cpu24 | 32,768 | 1,024 | MTP | editing | 106.06 | 58.78 | 4222.57 | 7.76 | 17.41 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-cpu0-after24 | 32,768 | 1,024 | MTP | coding | 122.21 | 62.70 | 4122.44 | 7.95 | 16.33 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-cpu0-after24 | 32,768 | 1,024 | MTP | editing | 105.89 | 58.74 | 4224.53 | 7.76 | 17.43 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-pool7-cpu8 | 32,768 | 1,024 | MTP | coding | 123.25 | 63.09 | 4138.00 | 7.92 | 16.23 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-pool7-cpu8 | 32,768 | 1,024 | MTP | editing | 106.31 | 58.86 | 4223.12 | 7.76 | 17.39 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-pool7-cpu0 | 32,768 | 1,024 | MTP | coding | 122.75 | 62.80 | 4117.62 | 7.96 | 16.30 | Exact output and recorded work versus paired control |
| 32768-mtp-worker-pool7-cpu0 | 32,768 | 1,024 | MTP | editing | 105.72 | 58.68 | 4223.28 | 7.76 | 17.45 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex-on-repeat | 32,768 | 1,024 | MTP | coding | 130.51 | 64.80 | 4120.52 | 7.95 | 15.80 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex-on-repeat | 32,768 | 1,024 | MTP | editing | 112.21 | 60.63 | 4223.55 | 7.76 | 16.88 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex-off-repeat | 32,768 | 1,024 | MTP | coding | 121.77 | 62.56 | 4119.90 | 7.95 | 16.36 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex-off-repeat | 32,768 | 1,024 | MTP | editing | 105.53 | 58.63 | 4223.17 | 7.76 | 17.46 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex-on-repeat | 131,072 | 1,024 | MTP | coding | 131.93 | 25.64 | 4075.95 | 32.16 | 39.92 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex-on-repeat | 131,072 | 1,024 | MTP | editing | 106.12 | 24.55 | 4089.38 | 32.05 | 41.70 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex-off-repeat | 131,072 | 1,024 | MTP | coding | 124.95 | 25.36 | 4075.18 | 32.16 | 40.36 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex-off-repeat | 131,072 | 1,024 | MTP | editing | 100.30 | 24.21 | 4086.10 | 32.08 | 42.29 | Exact output and recorded work versus paired control |
| 32768-plain-duplex-on-repeat | 32,768 | 1,024 | Plain | coding | 73.80 | 47.05 | 4155.74 | 7.88 | 21.76 | Exact output and recorded work versus paired control |
| 32768-plain-duplex-on-repeat | 32,768 | 1,024 | Plain | editing | 61.99 | 42.24 | 4243.35 | 7.72 | 24.24 | Exact output and recorded work versus paired control |
| 32768-plain-duplex-off-repeat | 32,768 | 1,024 | Plain | coding | 71.71 | 46.18 | 4152.05 | 7.89 | 22.17 | Exact output and recorded work versus paired control |
| 32768-plain-duplex-off-repeat | 32,768 | 1,024 | Plain | editing | 60.52 | 41.52 | 4234.30 | 7.74 | 24.66 | Exact output and recorded work versus paired control |
| 131072-plain-duplex-on-repeat | 131,072 | 1,024 | Plain | coding | 74.88 | 22.35 | 4079.97 | 32.13 | 45.80 | Exact output and recorded work versus paired control |
| 131072-plain-duplex-on-repeat | 131,072 | 1,024 | Plain | editing | 59.62 | 20.80 | 4090.98 | 32.04 | 49.22 | Exact output and recorded work versus paired control |
| 131072-plain-duplex-off-repeat | 131,072 | 1,024 | Plain | coding | 73.13 | 22.19 | 4078.32 | 32.14 | 46.14 | Exact output and recorded work versus paired control |
| 131072-plain-duplex-off-repeat | 131,072 | 1,024 | Plain | editing | 58.28 | 20.63 | 4089.61 | 32.05 | 49.62 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex-worker-cpu16-pool15 | 32,768 | 1,024 | MTP | coding | 131.28 | 65.10 | 4134.61 | 7.93 | 15.73 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex-worker-cpu16-pool15 | 32,768 | 1,024 | MTP | editing | 112.44 | 60.71 | 4225.62 | 7.75 | 16.86 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex-worker-cpu8-pool7 | 32,768 | 1,024 | MTP | coding | 131.01 | 64.95 | 4123.99 | 7.95 | 15.76 | Exact output and recorded work versus paired control |
| 32768-mtp-duplex-worker-cpu8-pool7 | 32,768 | 1,024 | MTP | editing | 112.85 | 60.81 | 4222.84 | 7.76 | 16.83 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex-worker-cpu16-pool15 | 131,072 | 1,024 | MTP | coding | 133.08 | 25.70 | 4078.03 | 32.14 | 39.84 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex-worker-cpu16-pool15 | 131,072 | 1,024 | MTP | editing | 106.89 | 24.57 | 4085.70 | 32.08 | 41.66 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex-worker-cpu8-pool7 | 131,072 | 1,024 | MTP | coding | 132.79 | 25.68 | 4077.52 | 32.15 | 39.86 | Exact output and recorded work versus paired control |
| 131072-mtp-duplex-worker-cpu8-pool7 | 131,072 | 1,024 | MTP | editing | 106.56 | 24.56 | 4086.45 | 32.07 | 41.68 | Exact output and recorded work versus paired control |
| 32768-plain-default-off | 32,768 | 1,024 | Plain | coding | 73.64 | 47.00 | 4160.01 | 7.88 | 21.78 | Exact output and recorded work versus paired control |
| 32768-plain-default-off | 32,768 | 1,024 | Plain | editing | 61.96 | 42.23 | 4245.49 | 7.72 | 24.25 | Exact output and recorded work versus paired control |
| 32768-mtp-default-off | 32,768 | 1,024 | MTP | coding | 129.52 | 64.68 | 4137.01 | 7.92 | 15.83 | Exact output and recorded work versus paired control |
| 32768-mtp-default-off | 32,768 | 1,024 | MTP | editing | 112.19 | 60.64 | 4225.13 | 7.76 | 16.88 | Exact output and recorded work versus paired control |
| 32768-mtp-deferred-thread | 32,768 | 1,024 | MTP | coding | 129.57 | 64.52 | 4115.55 | 7.96 | 15.87 | Exact output and recorded work versus paired control |
| 32768-mtp-deferred-thread | 32,768 | 1,024 | MTP | editing | 111.86 | 60.53 | 4223.44 | 7.76 | 16.91 | Exact output and recorded work versus paired control |
| 32768-mtp-deferred-inline | 32,768 | 1,024 | MTP | coding | 130.52 | 64.83 | 4124.20 | 7.95 | 15.79 | Exact output and recorded work versus paired control |
| 32768-mtp-deferred-inline | 32,768 | 1,024 | MTP | editing | 112.67 | 60.75 | 4220.94 | 7.76 | 16.85 | Exact output and recorded work versus paired control |
| 32768-plain-deferred-inline | 32,768 | 1,024 | Plain | coding | 73.56 | 47.00 | 4167.58 | 7.86 | 21.78 | Exact output and recorded work versus paired control |
| 32768-plain-deferred-inline | 32,768 | 1,024 | Plain | editing | 61.93 | 42.21 | 4244.50 | 7.72 | 24.25 | Exact output and recorded work versus paired control |
| 131072-mtp-deferred-thread | 131,072 | 1,024 | MTP | coding | 132.19 | 25.67 | 4078.89 | 32.13 | 39.88 | Exact output and recorded work versus paired control |
| 131072-mtp-deferred-thread | 131,072 | 1,024 | MTP | editing | 106.44 | 24.55 | 4087.54 | 32.07 | 41.69 | Exact output and recorded work versus paired control |
| 131072-mtp-deferred-inline | 131,072 | 1,024 | MTP | coding | 132.25 | 25.65 | 4075.51 | 32.16 | 39.90 | Exact output and recorded work versus paired control |
| 131072-mtp-deferred-inline | 131,072 | 1,024 | MTP | editing | 106.55 | 24.55 | 4085.26 | 32.08 | 41.69 | Exact output and recorded work versus paired control |
| 131072-plain-deferred-inline | 131,072 | 1,024 | Plain | coding | 74.47 | 22.30 | 4075.81 | 32.16 | 45.91 | Exact output and recorded work versus paired control |
| 131072-plain-deferred-inline | 131,072 | 1,024 | Plain | editing | 59.79 | 20.82 | 4090.90 | 32.04 | 49.17 | Exact output and recorded work versus paired control |
| 32768-ngram-deferred-inline | 32,768 | 1,024 | Plain+ngram | coding | 75.42 | 47.49 | 4107.66 | 7.98 | 21.55 | * First output difference at token 268; work may differ |
| 32768-ngram-deferred-inline | 32,768 | 1,024 | Plain+ngram | editing | 99.22 | 56.70 | 4236.77 | 7.73 | 18.05 | * Matching output; speculative work differs |
| 131072-ngram-deferred-inline | 131,072 | 1,024 | Plain+ngram | coding | 75.38 | 22.38 | 4077.40 | 32.15 | 45.73 | * First output difference at token 221; work may differ |
| 131072-ngram-deferred-inline | 131,072 | 1,024 | Plain+ngram | editing | 102.26 | 24.40 | 4104.39 | 31.93 | 41.95 | * Matching output; speculative work differs |
| 32768-mtp-ngram-deferred-inline | 32,768 | 1,024 | MTP+ngram | coding | 129.74 | 64.74 | 4137.63 | 7.92 | 15.81 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-deferred-inline | 32,768 | 1,024 | MTP+ngram | editing | 110.07 | 60.04 | 4229.22 | 7.75 | 17.05 | * Matching output; speculative work differs |
| 131072-mtp-ngram-deferred-inline | 131,072 | 1,024 | MTP+ngram | coding | 131.97 | 25.65 | 4078.12 | 32.14 | 39.90 | * Matching output; speculative work differs |
| 131072-mtp-ngram-deferred-inline | 131,072 | 1,024 | MTP+ngram | editing | 103.44 | 24.40 | 4089.10 | 32.05 | 41.95 | * Matching output; speculative work differs |
| 32768-plain-reuse-off | 32,768 | 1,024 | Plain | coding | 73.61 | 46.91 | 4139.67 | 7.92 | 21.83 | Exact output and recorded work versus paired control |
| 32768-plain-reuse-off | 32,768 | 1,024 | Plain | editing | 61.91 | 42.23 | 4252.71 | 7.71 | 24.24 | Exact output and recorded work versus paired control |
| 32768-plain-reuse-on | 32,768 | 1,024 | Plain | coding | 72.51 | 46.51 | 4154.16 | 7.89 | 22.01 | Exact output and recorded work versus paired control |
| 32768-plain-reuse-on | 32,768 | 1,024 | Plain | editing | 61.13 | 41.83 | 4242.75 | 7.72 | 24.47 | Exact output and recorded work versus paired control |
| 32768-mtp-reuse-off | 32,768 | 1,024 | MTP | coding | 129.04 | 64.58 | 4138.99 | 7.92 | 15.85 | Exact output and recorded work versus paired control |
| 32768-mtp-reuse-off | 32,768 | 1,024 | MTP | editing | 111.93 | 60.56 | 4224.42 | 7.76 | 16.91 | Exact output and recorded work versus paired control |
| 32768-mtp-reuse-on | 32,768 | 1,024 | MTP | coding | 129.06 | 64.57 | 4137.84 | 7.92 | 15.85 | Exact output and recorded work versus paired control |
| 32768-mtp-reuse-on | 32,768 | 1,024 | MTP | editing | 111.35 | 60.37 | 4222.90 | 7.76 | 16.96 | Exact output and recorded work versus paired control |
| 32768-ngram-reuse-off | 32,768 | 1,024 | Plain+ngram | coding | 75.03 | 47.53 | 4153.11 | 7.89 | 21.54 | Exact output and recorded work versus paired control |
| 32768-ngram-reuse-off | 32,768 | 1,024 | Plain+ngram | editing | 105.17 | 58.63 | 4242.80 | 7.72 | 17.46 | * Matching output; speculative work differs |
| 32768-ngram-reuse-on | 32,768 | 1,024 | Plain+ngram | coding | 74.44 | 47.31 | 4155.90 | 7.88 | 21.64 | * Matching output; speculative work differs |
| 32768-ngram-reuse-on | 32,768 | 1,024 | Plain+ngram | editing | 106.65 | 59.11 | 4246.70 | 7.72 | 17.32 | * Matching output; speculative work differs |
| 32768-mtp-ngram-reuse-off | 32,768 | 1,024 | MTP+ngram | coding | 130.29 | 64.74 | 4119.90 | 7.95 | 15.81 | * First output difference at token 122; work may differ |
| 32768-mtp-ngram-reuse-off | 32,768 | 1,024 | MTP+ngram | editing | 111.27 | 60.32 | 4217.68 | 7.77 | 16.97 | * Matching output; speculative work differs |
| 32768-mtp-ngram-reuse-on | 32,768 | 1,024 | MTP+ngram | coding | 129.67 | 64.73 | 4138.89 | 7.92 | 15.81 | * First output difference at token 122; work may differ |
| 32768-mtp-ngram-reuse-on | 32,768 | 1,024 | MTP+ngram | editing | 107.60 | 59.26 | 4223.66 | 7.76 | 17.27 | * Matching output; speculative work differs |
| 32768-mtp-direct-reuse-off | 32,768 | 1,024 | MTP | coding | 118.51 | 61.84 | 4140.04 | 7.91 | 16.56 | Exact output and recorded work versus paired control |
| 32768-mtp-direct-reuse-off | 32,768 | 1,024 | MTP | editing | 97.45 | 56.06 | 4225.62 | 7.75 | 18.26 | Exact output and recorded work versus paired control |
| 32768-mtp-direct-reuse-on | 32,768 | 1,024 | MTP | coding | 97.49 | 55.57 | 4138.00 | 7.92 | 18.42 | Exact output and recorded work versus paired control |
| 32768-mtp-direct-reuse-on | 32,768 | 1,024 | MTP | editing | 77.88 | 48.98 | 4225.73 | 7.75 | 20.90 | Exact output and recorded work versus paired control |
| 32768-plain-pcie-1 | 32,768 | 1,024 | Plain | coding | 60.58 | 41.25 | 4140.25 | 7.91 | 24.82 | * First output difference at token 122; work may differ |
| 32768-plain-pcie-1 | 32,768 | 1,024 | Plain | editing | 45.99 | 34.13 | 4236.55 | 7.73 | 30.00 | * Matching output; speculative work differs |
| 32768-mtp-pcie-1 | 32,768 | 1,024 | MTP | coding | 98.30 | 55.83 | 4138.00 | 7.92 | 18.34 | * First output difference at token 473; work may differ |
| 32768-mtp-pcie-1 | 32,768 | 1,024 | MTP | editing | 78.16 | 49.06 | 4218.49 | 7.77 | 20.87 | * Matching output; speculative work differs |
| 32768-ngram-pcie-1 | 32,768 | 1,024 | Plain+ngram | coding | 60.81 | 41.39 | 4149.74 | 7.90 | 24.74 | * First output difference at token 173; work may differ |
| 32768-ngram-pcie-1 | 32,768 | 1,024 | Plain+ngram | editing | 75.32 | 48.01 | 4239.18 | 7.73 | 21.33 | * Matching output; speculative work differs |
| 32768-mtp-ngram-pcie-1 | 32,768 | 1,024 | MTP+ngram | coding | 98.09 | 55.71 | 4128.20 | 7.94 | 18.38 | * First output difference at token 311; work may differ |
| 32768-mtp-ngram-pcie-1 | 32,768 | 1,024 | MTP+ngram | editing | 74.18 | 47.46 | 4219.58 | 7.77 | 21.57 | * Matching output; speculative work differs |
| 32768-plain-control | 32,768 | 512 | Plain | coding | 71.00 | 33.93 | 4160.86 | 7.88 | 15.09 | Reference / no paired check in this record |
| 32768-plain-dram | 32,768 | 512 | Plain | coding | 67.65 | 33.14 | 4159.11 | 7.88 | 15.45 | Exact output and recorded work versus paired control |
| 32768-plain-pcie | 32,768 | 512 | Plain | coding | 67.90 | 33.18 | 4155.63 | 7.89 | 15.43 | Exact output and recorded work versus paired control |
| 32768-mtp-control | 32,768 | 512 | MTP | coding | 115.66 | 41.36 | 4123.47 | 7.95 | 12.37 | Reference / no paired check in this record |
| 32768-mtp-dram | 32,768 | 512 | MTP | coding | 106.35 | 40.08 | 4119.01 | 7.96 | 12.77 | Exact output and recorded work versus paired control |
| 32768-mtp-pcie | 32,768 | 512 | MTP | coding | 107.43 | 40.34 | 4137.27 | 7.92 | 12.69 | Exact output and recorded work versus paired control |
| 32768-ngram-control | 32,768 | 512 | Plain+ngram | editing | 69.31 | 33.52 | 4156.90 | 7.88 | 15.27 | Reference / no paired check in this record |
| 32768-ngram-dram | 32,768 | 512 | Plain+ngram | editing | 64.24 | 32.30 | 4159.38 | 7.88 | 15.85 | * Matching output; speculative work differs |
| 32768-ngram-pcie | 32,768 | 512 | Plain+ngram | editing | 64.42 | 32.31 | 4151.00 | 7.89 | 15.84 | * Matching output; speculative work differs |
| 32768-mtp-ngram-control | 32,768 | 512 | MTP+ngram | editing | 66.90 | 32.78 | 4116.69 | 7.96 | 15.61 | Reference / no paired check in this record |
| 32768-mtp-ngram-dram | 32,768 | 512 | MTP+ngram | editing | 63.78 | 32.09 | 4135.86 | 7.92 | 15.95 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-pcie | 32,768 | 512 | MTP+ngram | editing | 63.86 | 32.12 | 4138.00 | 7.92 | 15.94 | Exact output and recorded work versus paired control |
| 32768-plain-pcie-0 | 32,768 | 1,024 | Plain | coding | 73.91 | 47.06 | 4146.17 | 7.90 | 21.76 | * First output difference at token 120; work may differ |
| 32768-plain-pcie-0 | 32,768 | 1,024 | Plain | editing | 62.67 | 42.55 | 4242.91 | 7.72 | 24.06 | * Matching output; speculative work differs |
| 32768-mtp-pcie-0 | 32,768 | 1,024 | MTP | coding | 138.05 | 66.38 | 4094.26 | 8.00 | 15.42 | * First output difference at token 120; work may differ |
| 32768-mtp-pcie-0 | 32,768 | 1,024 | MTP | editing | 115.99 | 61.68 | 4217.63 | 7.77 | 16.60 | * Matching output; speculative work differs |
| 32768-ngram-pcie-0 | 32,768 | 1,024 | Plain+ngram | coding | 77.39 | 48.47 | 4152.95 | 7.89 | 21.12 | * First output difference at token 32; work may differ |
| 32768-ngram-pcie-0 | 32,768 | 1,024 | Plain+ngram | editing | 113.80 | 61.13 | 4229.17 | 7.75 | 16.75 | * Matching output; speculative work differs |
| 32768-mtp-ngram-pcie-0 | 32,768 | 1,024 | MTP+ngram | coding | 134.12 | 65.81 | 4137.32 | 7.92 | 15.56 | * First output difference at token 120; work may differ |
| 32768-mtp-ngram-pcie-0 | 32,768 | 1,024 | MTP+ngram | editing | 112.22 | 60.60 | 4218.71 | 7.77 | 16.89 | * Matching output; speculative work differs |
| 32768-plain-retained-trace | 32,768 | 1,024 | Plain | coding | 73.49 | 46.95 | 4161.60 | 7.87 | 21.81 | Exact output and recorded work versus paired control |
| 32768-plain-retained-trace | 32,768 | 1,024 | Plain | editing | 61.79 | 42.16 | 4250.34 | 7.71 | 24.28 | Exact output and recorded work versus paired control |
| 32768-mtp-retained-trace | 32,768 | 1,024 | MTP | coding | 130.01 | 64.85 | 4142.60 | 7.91 | 15.79 | Exact output and recorded work versus paired control |
| 32768-mtp-retained-trace | 32,768 | 1,024 | MTP | editing | 112.04 | 60.59 | 4224.31 | 7.76 | 16.90 | Exact output and recorded work versus paired control |
| 32768-ngram-retained-trace | 32,768 | 1,024 | Plain+ngram | coding | 74.97 | 47.54 | 4159.59 | 7.88 | 21.54 | * First output difference at token 292; work may differ |
| 32768-ngram-retained-trace | 32,768 | 1,024 | Plain+ngram | editing | 96.54 | 55.88 | 4247.70 | 7.71 | 18.32 | * Matching output; speculative work differs |
| 32768-mtp-ngram-retained-trace | 32,768 | 1,024 | MTP+ngram | coding | 129.96 | 64.64 | 4118.03 | 7.96 | 15.84 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-retained-trace | 32,768 | 1,024 | MTP+ngram | editing | 110.84 | 60.20 | 4219.31 | 7.77 | 17.00 | * Matching output; speculative work differs |
| 32768-mtp-retained-0 | 32,768 | 1,024 | MTP | coding | 130.51 | 64.94 | 4138.84 | 7.92 | 15.76 | Exact output and recorded work versus paired control |
| 32768-mtp-retained-0 | 32,768 | 1,024 | MTP | editing | 112.22 | 60.62 | 4220.61 | 7.76 | 16.89 | Exact output and recorded work versus paired control |
| 32768-mtp-retained-8 | 32,768 | 1,024 | MTP | coding | 129.39 | 64.50 | 4118.08 | 7.96 | 15.87 | Exact output and recorded work versus paired control |
| 32768-mtp-retained-8 | 32,768 | 1,024 | MTP | editing | 110.38 | 60.08 | 4221.37 | 7.76 | 17.04 | Exact output and recorded work versus paired control |
| 32768-mtp-cpu-repeat | 32,768 | 1,024 | MTP | coding | 135.64 | 66.27 | 4148.48 | 7.90 | 15.45 | Exact output and recorded work versus paired control |
| 32768-mtp-cpu-repeat | 32,768 | 1,024 | MTP | editing | 114.50 | 61.26 | 4219.04 | 7.77 | 16.71 | Exact output and recorded work versus paired control |
| 32768-mtp-auto-repeat | 32,768 | 1,024 | MTP | coding | 130.29 | 64.80 | 4128.04 | 7.94 | 15.80 | * First output difference at token 120; work may differ |
| 32768-mtp-auto-repeat | 32,768 | 1,024 | MTP | editing | 111.98 | 60.55 | 4221.92 | 7.76 | 16.91 | * Matching output; speculative work differs |
| 32768-ngram-cpu-repeat | 32,768 | 1,024 | Plain+ngram | coding | 75.98 | 47.95 | 4162.02 | 7.87 | 21.35 | * First output difference at token 481; work may differ |
| 32768-ngram-cpu-repeat | 32,768 | 1,024 | Plain+ngram | editing | 110.51 | 60.23 | 4238.74 | 7.73 | 17.00 | * Matching output; speculative work differs |

## pcie-repeat-live.json records

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-ngram-auto-repeat | 32,768 | 1,024 | Plain+ngram | coding | 74.50 | 47.25 | 4134.50 | 7.93 | 21.67 | * First output difference at token 32; work may differ |
| 32768-ngram-auto-repeat | 32,768 | 1,024 | Plain+ngram | editing | 100.67 | 57.20 | 4241.81 | 7.72 | 17.90 | * Matching output; speculative work differs |
| 131072-plain-auto-repeat | 131,072 | 1,024 | Plain | coding | 74.83 | 22.35 | 4081.42 | 32.11 | 45.80 | Reference / no paired check in this record |
| 131072-plain-auto-repeat | 131,072 | 1,024 | Plain | editing | 59.85 | 20.82 | 4088.07 | 32.06 | 49.17 | Reference / no paired check in this record |
| 131072-plain-cpu-repeat | 131,072 | 1,024 | Plain | coding | 74.94 | 22.36 | 4081.56 | 32.11 | 45.78 | * First output difference at token 221; work may differ |
| 131072-plain-cpu-repeat | 131,072 | 1,024 | Plain | editing | 60.38 | 20.92 | 4099.19 | 31.98 | 48.94 | * Matching output; speculative work differs |
| 131072-mtp-auto-repeat | 131,072 | 1,024 | MTP | coding | 131.82 | 25.66 | 4079.77 | 32.13 | 39.90 | Reference / no paired check in this record |
| 131072-mtp-auto-repeat | 131,072 | 1,024 | MTP | editing | 106.25 | 24.53 | 4084.44 | 32.09 | 41.73 | Reference / no paired check in this record |
| 131072-mtp-cpu-repeat | 131,072 | 1,024 | MTP | coding | 137.16 | 25.82 | 4073.86 | 32.17 | 39.64 | * First output difference at token 221; work may differ |
| 131072-mtp-cpu-repeat | 131,072 | 1,024 | MTP | editing | 110.44 | 24.79 | 4093.49 | 32.02 | 41.29 | * Matching output; speculative work differs |
| 131072-ngram-auto-repeat | 131,072 | 1,024 | Plain+ngram | coding | 74.41 | 22.32 | 4083.58 | 32.10 | 45.86 | Reference / no paired check in this record |
| 131072-ngram-auto-repeat | 131,072 | 1,024 | Plain+ngram | editing | 102.50 | 24.38 | 4095.81 | 32.00 | 41.99 | Reference / no paired check in this record |
| 131072-ngram-cpu-repeat | 131,072 | 1,024 | Plain+ngram | coding | 74.75 | 22.33 | 4078.93 | 32.13 | 45.83 | * First output difference at token 308; work may differ |
| 131072-ngram-cpu-repeat | 131,072 | 1,024 | Plain+ngram | editing | 104.34 | 24.53 | 4107.17 | 31.91 | 41.73 | * Matching output; speculative work differs |
| 131072-mtp-ngram-auto-repeat | 131,072 | 1,024 | MTP+ngram | coding | 131.76 | 25.64 | 4077.11 | 32.15 | 39.92 | Reference / no paired check in this record |
| 131072-mtp-ngram-auto-repeat | 131,072 | 1,024 | MTP+ngram | editing | 102.86 | 24.36 | 4087.61 | 32.07 | 42.02 | Reference / no paired check in this record |
| 131072-mtp-ngram-cpu-repeat | 131,072 | 1,024 | MTP+ngram | coding | 134.82 | 25.74 | 4074.18 | 32.17 | 39.77 | * First output difference at token 221; work may differ |
| 131072-mtp-ngram-cpu-repeat | 131,072 | 1,024 | MTP+ngram | editing | 110.13 | 24.75 | 4087.75 | 32.06 | 41.36 | * Matching output; speculative work differs |

## cache-diagnostic-live.json rtxpro-q8-miss-trace-20261004

**Diagnostic: timings are not comparable serving benchmarks.**

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-miss-trace | 32,768 | 1,024 | MTP | coding | 130.62 | 64.82 | 4119.38 | 7.95 | 15.79 | Exact output and recorded work versus paired control |
| 32768-mtp-miss-trace | 32,768 | 1,024 | MTP | editing | 112.26 | 60.64 | 4222.95 | 7.76 | 16.88 | Exact output and recorded work versus paired control |

## readonly-model-live.json records

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-plain-readonly-0 | 32,768 | 1,024 | Plain | coding | 73.70 | 47.04 | 4163.39 | 7.87 | 21.76 | Exact output and recorded work versus paired control |
| 32768-plain-readonly-0 | 32,768 | 1,024 | Plain | editing | 61.87 | 42.19 | 4245.49 | 7.72 | 24.27 | Exact output and recorded work versus paired control |
| 32768-plain-readonly-4 | 32,768 | 1,024 | Plain | coding | 73.53 | 46.95 | 4158.06 | 7.88 | 21.81 | Exact output and recorded work versus paired control |
| 32768-plain-readonly-4 | 32,768 | 1,024 | Plain | editing | 62.32 | 42.39 | 4245.05 | 7.72 | 24.15 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-0 | 32,768 | 1,024 | MTP | coding | 130.01 | 64.87 | 4145.70 | 7.90 | 15.78 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-0 | 32,768 | 1,024 | MTP | editing | 111.92 | 60.55 | 4224.15 | 7.76 | 16.91 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-4 | 32,768 | 1,024 | MTP | coding | 132.69 | 65.08 | 4090.43 | 8.01 | 15.73 | Exact output and recorded work versus paired control |
| 32768-mtp-readonly-4 | 32,768 | 1,024 | MTP | editing | 113.79 | 61.09 | 4223.17 | 7.76 | 16.76 | Exact output and recorded work versus paired control |
| 32768-ngram-readonly-0 | 32,768 | 1,024 | Plain+ngram | coding | 74.96 | 47.43 | 4138.16 | 7.92 | 21.58 | * First output difference at token 557; work may differ |
| 32768-ngram-readonly-0 | 32,768 | 1,024 | Plain+ngram | editing | 100.18 | 57.00 | 4233.76 | 7.74 | 17.96 | * Matching output; speculative work differs |
| 32768-ngram-readonly-4 | 32,768 | 1,024 | Plain+ngram | coding | 74.53 | 47.35 | 4156.27 | 7.88 | 21.62 | * First output difference at token 173; work may differ |
| 32768-ngram-readonly-4 | 32,768 | 1,024 | Plain+ngram | editing | 106.31 | 59.05 | 4252.77 | 7.71 | 17.34 | * Matching output; speculative work differs |
| 32768-mtp-ngram-readonly-0 | 32,768 | 1,024 | MTP+ngram | coding | 129.78 | 64.74 | 4136.33 | 7.92 | 15.81 | * First output difference at token 122; work may differ |
| 32768-mtp-ngram-readonly-0 | 32,768 | 1,024 | MTP+ngram | editing | 108.84 | 59.65 | 4226.77 | 7.75 | 17.16 | * Matching output; speculative work differs |
| 32768-mtp-ngram-readonly-4 | 32,768 | 1,024 | MTP+ngram | coding | 131.18 | 65.10 | 4138.00 | 7.92 | 15.72 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-readonly-4 | 32,768 | 1,024 | MTP+ngram | editing | 112.49 | 60.75 | 4229.55 | 7.75 | 16.85 | * Matching output; speculative work differs |
