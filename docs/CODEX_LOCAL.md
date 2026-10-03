# Local Codex CLI with Strata

Use Codex CLI **0.160.0** with the explicit profile in [codex/strata.config.toml](codex/strata.config.toml).
This is a qualified, bounded local-model profile, not universal Codex compatibility.
Shell commands and file edits run on the computer running Codex; generation runs on the Strata server.

1. Start your configured native Strata server with `--experimental-responses`, an API key,
   and `STRATA_RESPONSES_REPLAY_KEY` as described in [RESPONSES.md](RESPONSES.md).
   Use the gbnf-v4 build and install requirements-json.txt for Codex automatic JSON titles;
   see [JSON_OUTPUT.md](JSON_OUTPUT.md).
   For coding with thinking enabled, merge [server-coding-settings.json](codex/server-coding-settings.json)
   into the existing server config. It is a settings fragment, not a complete model config.
2. Copy [strata.config.toml](codex/strata.config.toml) into your chosen Codex home as
   `strata.config.toml`. Replace its two `/ABSOLUTE/PATH/TO/...` paths with the downloaded
   [model catalog](codex/model-catalog-0.160.0.json) and [instructions](codex/local-model-instructions.txt).
   Replace the base URL with your authenticated server URL, or the loopback address of your SSH tunnel.
3. Set `STRATA_API_KEY` in the Codex process environment. Start the pinned client:

   ```powershell
   codex --no-daemon --strict-config --profile strata --sandbox workspace-write --ask-for-approval on-request --cd C:\path\to\project
   ```

4. Check that the selected model is `qwen3.8-flash-next` with medium reasoning and no
   missing-metadata warning. Ask it to read a small file, make a change, and run a focused test.
   You can interrupt a turn, change permissions, and send a new instruction. Use `/quit` to exit Codex.

The catalog states the **configured 32768-token context**, text-only Responses input,
and the supported reasoning levels. Keep its context fields aligned with your server configuration.
It preserves the previously tested unified-exec tool selection; freeform/Lark `apply_patch`
is not enabled. The instructions use the declared shell tool for edits and tell the model to
inspect failed or empty results rather than repeating an unchanged command.
The catalog is pinned to the client's format: do not substitute a catalog from a different release.
The `model_catalog_json` and named-profile settings are documented in the
[official OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

The coding defaults are temperature **1.0**, top-p **0.95**, top-k **20**, min-p **0**,
no presence/frequency penalty, repetition penalty **1.0** (off), and medium reasoning.
The local thinking budget is **2048 tokens**; it is a ceiling, not a target.
These sampling values follow the model author's
[thinking-mode recommendation](https://huggingface.co/Qwen/Qwen3.8-Flash-Next#best-practices).
They are a starting point for this Coder quantization, not a measured universal optimum.
For non-thinking mode the model card gives different sampling defaults; changing `/model`
effort does not change the server's sampling config automatically.

The earlier disposable launcher used temperature 0 (greedy), a 256-token thinking budget,
and fallback Codex metadata with no reasoning effort selected. The new profile explicitly
selects medium reasoning. A requested summary costs a second bounded generation; latency is
not equivalent to an answer-only request. Sampling and instructions can reduce repetitive
behavior but cannot guarantee that the model never loops or makes a bad tool choice.

Steering can introduce developer/system messages after earlier user turns. The Responses
adapter gathers these into the native template's leading instruction block in their original
order, retaining their roles. It does not downgrade permission updates into user messages.
The relative order of conversation messages and matched tool results is preserved, and the
supplied request is not mutated. Changing that prefix can reduce prompt-cache reuse.
A completed reasoning item can survive cancellation without a completed answer item;
Strata preserves it as an assistant thinking turn without inventing answer text.

The remaining protocol limits in [RESPONSES.md](RESPONSES.md) still apply: `store:false`,
full-history replay, non-strict function tools, no hosted tools, no image input, and no
strict function parameter schemas/Lark tools or server compaction endpoint. Native JSON
answer schemas are supported by the stacked GBNF build. This catalog does not enable
those capabilities or modify a client's requested schema. Long-session compaction is not
qualified; start a new conversation when approaching the configured context limit.
Keep the same replay key if you need to replay an earlier encrypted reasoning item. Fresh
keys invalidate older replay items. A LAN deployment must retain authentication; SSH forwarding
lets the model server remain bound to loopback.
