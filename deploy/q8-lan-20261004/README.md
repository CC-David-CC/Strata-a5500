# Frozen Q8 LAN test endpoint

This is David's experimental configuration of
[Niko1221/Strata](https://github.com/Niko1221/Strata), running on **llm-60's
RTX PRO 6000 Blackwell Workstation Edition 96 GB**, with 128 GB system RAM.
The original license and upstream credit are retained.

## Connect

| Setting | Value |
|---|---|
| OpenAI-compatible base URL | `http://10.0.7.68:8095/v1` |
| Chat endpoint | `POST /v1/chat/completions` |
| Model ID | `flash-next-Q8_0` |
| Authentication | `Authorization: Bearer <your API key>` |
| Windows key file | `C:\Users\dflanag3\.config\fleet\q8-lan\api-key.txt` |
| Server secret | `/home/dflanag3/.config/strata/q8-lan-20261004/api.env` (mode 0600) |
| Runtime | Q8_0, FP16 KV, native RoPE, MTP on, n-gram off, text only |
| Context allocation | 139,264 positions; 131,072 input + 1,024 output tested |
| Concurrency | One active generation; other clients wait in FIFO order |

The engine reserves eight positions in addition to prompt plus requested output.
Chat-template tokens also count toward input. Over-limit requests are rejected;
they are not silently truncated. Prompt and conversation caches remain zero,
as in the fresh-request throughput configuration. The native engine lifecycle
suite separately covered checkpoint/STOP behavior at 32K.

PowerShell example (the secret is read from the private file, not pasted here):

```powershell
$apiKey = (Get-Content "$env:USERPROFILE\.config\fleet\q8-lan\api-key.txt" -Raw).Trim()
$body = @{ model = 'flash-next-Q8_0'; messages = @(@{ role = 'user'; content = 'Say hello.' }); max_tokens = 128; reasoning_effort = 'none' } | ConvertTo-Json -Depth 6
Invoke-RestMethod 'http://10.0.7.68:8095/v1/chat/completions' -Method Post -ContentType 'application/json' -Headers @{ Authorization = "Bearer $apiKey" } -Body $body
```

The test service is enabled for boot. The address is currently assigned by DHCP;
reserve **10.0.7.68** for Ethernet MAC **74:56:3c:b8:66:2c** in the router to
keep this endpoint and its bind address stable. No router, DNS, forwarding,
SSH or Tailscale settings were changed.
Port **8095/TCP** is for LAN clients only; no public forwarding is needed.

## Exact frozen setup

The active config is [config.json](config.json), copied from the completed
128K MTP per-layer-admission trial. Only HTTP binding, log path, allowed host
and server metadata were added; engine arguments and environment are unchanged.

- Engine source: `ac398f5eb349eca70a6fd61eea63e824f843c868`.
- Engine SHA256: `95290a8a30c5d8d8984b02b5b7fc3128c8d2745f139891e5bdb9a5a9b5e6a7b9`.
- Immutable source/build directory: `/home/dflanag3/src/q8-layer-admission-ac398f5e`.
- 15,472 primary expert slots, four immutable secondary slots per layer.
- 75.25 GiB primary expert VRAM, 0.934 GiB secondary cache, 44.28 GiB pinned
  RAM expert complement; the lookup table is locked in system RAM.
- Ownership rotation, duplex copies, miss-fetch overlap, copy grid 32 and
  per-layer admission enabled. PCIe fraction 0.55, 15 CPU workers.
- Verifier allocation 8, MTP maximum window 4, threshold 0.5.
- No cached-CPU rerouting, GPU-refill/layer combination, or untested optimization.

The launcher verifies the config and engine hashes and holds the existing fleet
GPU lock. Model files are inventoried by path, size and mtime in
[manifest.json](manifest.json); this deployment did not repeat a full model hash
pass. The existing Python environment was reused; no packages/drivers were
installed or upgraded. Its installed versions are in the manifest.

The public frozen profiles are **alternatives**, not merged flags. Each names
its own measured engine. [The index](../../docs/benchmarks/q8-frozen-20261004/profile-index.json)
lists 48 measured launch configurations. Do not pass a GPU-refill profile to
the layer-only engine or assume their gains combine.

## Access boundary

The Python server binds only `10.0.7.68:8095`; API/admin operations require its
key. The health endpoint and static web shell follow upstream's public-health
behavior. The separate `fleet_q8_lan` nftables table drops connections to this
address/port from outside the host's actual `10.0.0.0/17` LAN subnet. It neither
enables UFW nor changes existing SSH/Tailscale rules. The original firewall
snapshot is saved beside the remote config as `firewall-before.txt`.

## Verification and limits

[HTTP validation](http-validation.json) passed from the Windows workstation
over LAN: health, rejection of missing/wrong keys, authenticated model discovery,
non-stream response, SSE streaming, two clients with an observed queue and FIFO
completion, explicit socket disconnect, and a successful following request.
The engine stayed loaded without a service restart. These small checks validate
serving behavior; they are not a sustained-load or long-context HTTP benchmark.

The first test helper stopped at cancellation because Python's HTTP/1.0 client
had transferred the socket to its response object. No engine failure was
reported. The corrected helper retained the socket before reading the response;
the complete rerun passed. The initial artifact is preserved as
[harness attempt 1](http-validation-harness-attempt1.json).

See the [complete benchmark matrix](../../docs/Q8_FROZEN_MATRIX.md) for generation,
effective throughput, prefill, controls, matching-output qualifications and
resource savings. Large byte reductions are retained as useful results even
when generation speed barely changes. Energy savings were not measured.

## Manage or roll back

Run from PowerShell using the existing SSH alias:

```powershell
ssh llm-60 'systemctl status strata-q8-lan.service --no-pager'
ssh llm-60 'sudo systemctl stop strata-q8-lan.service'
ssh llm-60 'sudo systemctl start strata-q8-lan.service'
```

To remove automatic startup and the new access guard, preserving every file:

```powershell
ssh llm-60 'sudo systemctl disable --now strata-q8-lan.service'
ssh llm-60 'sudo systemctl stop strata-q8-lan-firewall.service'
```

Stop the model service before stopping its guard. Stopping the guard deletes
only the new `fleet_q8_lan` table. Existing files, model weights, private SSH,
old benchmark results and all source branches remain intact. Optimization
queues stay paused; starting this endpoint does not restart them.
