# hu-eli-mcp - Claude plugin

Hungarian law with verifiable citations, as a Claude plugin: national acts and decrees and
**municipal decrees** (önkormányzati rendeletek, e.g. local building regulations), read in
full as paged plain text with search and point-in-time versions, from the National
Legislation Database (Nemzeti Jogszabalytar, njt.jog.gov.hu).

This is the danzig666 fork of
[matematicsolutions/hu-eli-mcp](https://github.com/matematicsolutions/hu-eli-mcp). The
plugin runs the MCP server from one exact commit of this fork (the source archive URL in
`plugin.json`); `uv.lock`, next to the manifest, pins that archive and every dependency with
hashes. It also ships the `magyar-jogszabalyok` skill, which tells Claude which tool to use
for which kind of legislation and how to read long documents page by page.

What it covers: an act or other national instrument by type, year, issuer and serial; a
municipal decree by issuer (settlement, county or Budapest district, by name or code), year
and serial; the version in force on a given day; the lists of document types and issuers.
The full tool list is in the [main README](../README.md).

## Requirements

Claude Code or the Claude desktop app, and [uv](https://docs.astral.sh/uv/) on your
machine (its `uvx` installs the locked packages on first start and runs the server).

## Install

```
/plugin marketplace add danzig666/hu-eli-mcp#feat/local-decrees-plugin
/plugin install hu-eli-mcp@hu-eli-mcp
```

From a shell: `claude plugin marketplace add danzig666/hu-eli-mcp#feat/local-decrees-plugin`.
After merging the branch into `main`, `danzig666/hu-eli-mcp` without `#...` is enough.

The Claude desktop app reads the same settings: a plugin installed at user scope in Claude
Code is also available in the desktop app's local sessions (its plugin browser is behind
the "+" next to the prompt box).

To update to a newer commit: change the archive URL in `.claude-plugin/plugin.json` and
`pyproject.toml`, run `uv lock` in this folder, commit, then `/plugin marketplace update`.

## Data

The server runs on your machine. Each tool call sends your query to the Hungarian National Legislation Database (njt.jog.gov.hu)
and to nothing else; nothing goes to MateMatic or anyone else. Your query and the results also pass
through whatever model you use, the same way as any other message.

The standalone server can fetch a small configuration file (updated source addresses) from
the upstream repository's GitHub Releases on first use. The plugin turns that off
(`HU_ELI_RUNTIME_URL` set to empty in `plugin.json`), so it runs only the reviewed code with
its built-in source addresses and makes no request other than the tool calls above.

Two things are written locally, in your home directory:

- a response cache (`~/.matematic/cache/hu-eli`), so a repeated lookup does not hit
  the source again. The sources are published legislation.
- an audit log (`~/.matematic/audit/hu-eli-mcp.jsonl`), one line per tool call: the
  tool name, a SHA-256 hash of the input (not the input itself), result size, time
  and status.

Delete either folder at any time; `HU_ELI_CACHE_DIR` and `HU_ELI_AUDIT_DIR` move them.

## Licence

Apache-2.0, see [LICENSE](../LICENSE).
