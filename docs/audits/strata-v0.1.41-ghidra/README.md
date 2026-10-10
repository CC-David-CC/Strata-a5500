# Strata v0.1.41: limited Ghidra/MCP static review

Review date: 2026-10-10. Related request: [security audits, #544](https://github.com/Niko1221/Strata/issues/544).

No malware indicators were identified in the material examined. This finding is limited to the static checks below. It does not establish that the binaries are clean or safe: full program analysis and application-main decompilation did not complete, and no runtime or network behavior was observed.

## Scope and artifact identity

The examined artifacts were the two executables in the official [Windows x64 v0.1.41 release archive](https://github.com/Niko1221/Strata/releases/download/v0.1.41/strata-windows-x64.zip). Neither executable was run. This report does not cover other release packages, installers, Python dependencies, GPU driver libraries, model files, or subsequent releases.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| strata-windows-x64.zip | 137164559 | `3dd7715f4844c0f9d2f28eb5067af0198f386df060c93523cd17e1d65b757f13` |
| strata.exe | 164440576 | `17dabc6a49746aa22beebdf354923ba5eeb21affc6597c6976ac430e46671518` |
| strata-vision.exe | 108195840 | `a4a8488a45a19bdf10f0c550a4fddd980572ac9c355456f0412a06cfd57b4f75` |

Both executables are x64 PE files. Both have an empty Authenticode certificate directory and were reported as `NotSigned` by Windows `Get-AuthenticodeSignature`. Their bundled [BUILD.json](evidence/BUILD.json) identifies version 0.1.41, CUDA 13.0, and GPU architectures 75/86/89/120, but does not identify an exact source commit. No reproducible-build comparison or binary-to-source attestation was performed. The branch carrying this report is based on upstream commit `61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406`; that is not an asserted build commit for these executables.

## Checks and observations

The [PE evidence](evidence/pe-audit.json) records SHA-256, byte size, import tables, embedded ASCII URLs, exact marker counts, and certificate-directory size for both executables. Exact, case-sensitive ASCII probes for `powershell`, `cmd.exe`, `WinHttp`, `WinInet`, `URLDownloadToFile`, `WSAStartup`, and `ws2_32` returned zero occurrences. Each executable had two `nvcuda` occurrences and three `LoadLibrary` occurrences. These probes do not detect encoded, constructed, differently cased, or UTF-16 strings, delayed imports, or API resolution through other mechanisms. Zero matches are not evidence that a capability is absent.

The URL scan found no matching URLs in strata.exe. It found six llama.cpp GitHub issue, discussion, and pull-request URLs in strata-vision.exe; the exact strings are in the PE evidence. Embedded URLs do not establish that a program contacts them.

Ghidra 12.1.4 and the third-party GhidraMCP 6.0.0 plugin were used through the Python MCP SDK and stdio bridge. Tool and archive identities are in [downloads.json](evidence/downloads.json). Tool hashes identify the toolchain used; the tools themselves were not security-audited as part of this review.

Ghidra loaded strata.exe as `x86:LE:64:default`, Windows compiler convention, image base `140000000`. The initial metadata listed 7,570 functions and 7,751 symbols; a later incomplete-analysis status listed 8,455 functions. The entry function at `1404edefc` calls two startup routines. The successfully decompiled routines at `1404ee60c` and `1404edd80` are consistent with MSVC security-cookie initialization and CRT startup, respectively. The former combines time, process/thread IDs, a performance counter, and a stack address. The latter reaches a candidate application main at `1400511f0`. These runtime calls are not by themselves malware indicators.

### Incomplete analysis

The MCP GUI import endpoint failed in headless mode, so the server's `--file` loader was used. Whole-program `run_analysis` and decompilation of candidate main `1400511f0` returned inner `{"error": "timed out"}` payloads despite the outer MCP `isError` flag being false. The recorded analysis status is `analyzing: true`, `analyzed: false`. The [server log excerpts](evidence/analysis-log-excerpts.txt) also reported missing PDB information, an out-of-address-space analysis error at `14009f4a0`, and a plugin/script initialization null-pointer error. Full analysis therefore cannot be claimed.

The recorded Ghidra string search returned no matches while analysis was incomplete; this result is retained for transparency and is not used as evidence of absence. strata-vision.exe received the PE checks only, not Ghidra decompilation. Imported dependencies were not reverse-engineered. No dynamic sandboxing, network capture, antivirus assessment, comprehensive call-graph review, persistence review, or comparison against a local source build was performed.

## Reproduce the static checks

Use the exact archive and hashes above. Extract it into an artifact directory without launching the executables. The report contains no release binaries, Ghidra projects, JDK installation, or tool archives. Acquisition URLs, sizes, and recorded SHA-256 values are in `evidence/downloads.json`.

For PE checks, use Python with `pefile==2024.8.26`:

```powershell
python -m pip install pefile==2024.8.26
python docs/audits/strata-v0.1.41-ghidra/pe_checks.py --artifact-dir ./artifacts --output ./pe-audit.json
Get-AuthenticodeSignature ./artifacts/strata.exe, ./artifacts/strata-vision.exe |
    Select-Object Path, Status
```

The helper reads the two executables and writes JSON; it does not execute or download them. Compare its output with the checked-in PE evidence and verify the hashes before interpreting the observations.

For the Ghidra/MCP checks, install the versions identified in the acquisition manifest: Ghidra 12.1.4, Temurin JDK 21.0.12.1+1, GhidraMCP 6.0.0, its bridge wheel, and Python `mcp==1.30.0`. The following helper adapts the headless launch used in this review to explicit local paths. It binds only to loopback and runs in the foreground; stop it after the review. The headless/plugin errors documented above may recur.

```powershell
python docs/audits/strata-v0.1.41-ghidra/start_headless.py --ghidra-home ./tools/ghidra_12.1.4_PUBLIC --java ./tools/jdk-21.0.12.1+1/bin/java.exe --plugin-jar ./tools/GhidraMCP/lib/GhidraMCP-6.0.0.jar --artifact ./artifacts/strata.exe
```

In another terminal, use the MCP bridge with environment variable `GHIDRA_MCP_URL=http://127.0.0.1:8089` and stdio command `python -m bridge_mcp_ghidra --no-lazy`. Initialize a Python MCP SDK `ClientSession`, then call these tools with the arguments shown:

| Tool | Arguments |
| --- | --- |
| get_metadata | `{"program":"strata.exe"}` |
| get_entry_points | `{"program":"strata.exe"}` |
| list_imports | `{"program":"strata.exe","offset":0,"limit":500}` |
| run_analysis | `{"program":"strata.exe","dry_run":false}` |
| analysis_status | `{"program":"strata.exe"}` |
| decompile_function | `{"program":"strata.exe","address":"1404edefc","timeout":60}` |
| decompile_function | Repeat for `1404ee60c`, `1404edd80`, and `1400511f0` |

Check the inner result for errors as well as the outer MCP status. Analysis counts and generated decompilation can vary with analysis progress; these commands do not guarantee full analysis or reproduce a clean-binary conclusion.

## Evidence handling and validation

The log excerpts retain the relevant warning and error lines, with trailing whitespace removed. The MCP JSON responses are retained in `evidence/`, including unsuccessful operations. Only the local executable path in the metadata response was replaced with `<artifact-directory>/strata.exe`; the other recorded results were preserved. Tool archives, full server logs, project caches, and unrelated private artifacts are excluded.

Before publication, the PE helper was rerun against the original release executables and its JSON was compared with the original recorded PE evidence. All artifact hashes, imports, counts, URL strings, and certificate-directory sizes matched. The reproduction helpers were checked for Python syntax, and the headless launch helper's help interface was checked; the full Ghidra run was not repeated for publication. No Strata application or native backend code changes are included.
