# AntScope MCP — Plan

## Status: blocked, not yet plannable in detail

This sub-project targets a future AntScopeZ **application** API that doesn't exist yet — it's
currently undefined and being designed/built separately, in the `AntScopeZ` repo. There's no
concrete contract to plan or build against yet. This doc will get a real architecture/API
section once that API exists.

## What this actually is

An MCP server (and possibly a companion webapp) that lets an AI agent — and humans — drive
the **AntScopeZ desktop application** itself, through whatever API it eventually exposes.
This is about controlling the app, not the NanoVNA hardware directly.

**This is not `nanovna-mcp`.** Direct NanoVNA hardware control (over serial, bypassing
AntScopeZ entirely) is a separate, fully decoupled sub-project in this same repo — see
[`nanovna-mcp/README.md`](../nanovna-mcp/README.md), which is already implemented. The two
sub-projects have no dependency on each other.

## History — why this doc looks different from an earlier version

An earlier version of this plan (written 2026-09-03) described a small serial-passthrough API
daemon for direct NanoVNA hardware control, and treated `antscope-mcp` as that daemon's
consumer. That daemon was built, and its real identity became clear in the process: it's a
standalone NanoVNA-control project, not part of `antscope-mcp`. It now lives fully in this
repo as `nanovna-mcp` (implemented, see that folder's `README.md`).

Casey confirmed (2026-09-03) that coupling `antscope-mcp` to that daemon was a mistake —
`nanovna-mcp` should always have been separate. This doc was rewritten to drop that coupling
entirely rather than carry stale architecture/API details that now belong to `nanovna-mcp`.

## What's next

Nothing to build yet. Once the AntScopeZ application API is designed and available (tracked
in the `AntScopeZ` repo, not here), revisit this plan with the actual API contract in hand —
architecture, deployment scope, and the MCP tool surface all depend on what that API turns
out to look like.
