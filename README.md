# hu-eli-mcp (danzig666 fork)

<!-- mcp-name: io.github.matematicsolutions/hu-eli-mcp -->

Hungarian legislation with verifiable citations from the official **Nemzeti Jogszabálytár**
(NJT, `njt.jog.gov.hu`): national acts and decrees **and municipal decrees**
(önkormányzati rendeletek, e.g. a local building regulation, HÉSZ), addressed by their
native ELI and read **in full** as paged plain text with search and point-in-time versions.

This is a fork of [matematicsolutions/hu-eli-mcp](https://github.com/matematicsolutions/hu-eli-mcp)
(part of MateMatic's eu-legal-mcp line). The fork adds:

- **Complete text of long documents.** NJT lazy-loads parts of long laws and annexes; the
  first HTML of the Criminal Code stops at § 338. The fork fetches the deferred blocks and
  fails loudly instead of returning a silently truncated statute (offered upstream as
  PR #2 from branch `fix/load-complete-njt-text`).
- **Municipal decrees** by NJT's municipal ELI `/eli/OR/{year}/{issuer}/{serial}`, with the
  municipality given by name (`Debrecen`) or code.
- **Paged plain text with search**, so a 1-3 MB code is read page by page instead of being
  cut off by the client, plus versions in force on a given day.
- A **`hu-eli` command-line tool** with the same lookups.
- A **Claude plugin** (Claude Code, desktop app) pinned to one commit of this fork, and a
  **Claude chat skill** (claude.ai) that bundles the code, so a chat never downloads it.

> Branches: **`feat/local-decrees-plugin` is the current state** described here.
> `main` still matches upstream; `fix/load-complete-njt-text` is the upstream PR.

## Ways to use it

| Where | What to install | Section |
|---|---|---|
| claude.ai chats (and Projects) | the `njt-jogszabalyok` skill ZIP | [Claude chat skill](#claude-chat-skill) |
| Claude Code, Claude desktop app | the `hu-eli-mcp` plugin | [Claude plugin](#claude-plugin) |
| Any MCP client | the `hu-eli-mcp` server | [MCP server](#mcp-server) |
| A terminal or a script | the `hu-eli` command | [Command line](#command-line) |

All four use the same code (`src/hu_eli_mcp`) and send queries only to `njt.jog.gov.hu`.

## Claude chat skill

`skills/njt-jogszabalyok/` is a skill for chats on claude.ai. Claude runs the `hu-eli`
command in its code execution sandbox, reads the official text and cites it.

The hu-eli source is **bundled in the skill** (`vendor/`), pinned to one commit of this
repository. Installing it from GitHub inside a chat does not work reliably: code execution
treats a package downloaded from a GitHub URL as external code and can refuse to run it.
With the bundle, nothing is downloaded from GitHub; the only install is the three PyPI
dependencies on first use.

```
skills/
├── build_skill.py            builds the uploadable ZIP from a commit of this repo
└── njt-jogszabalyok/
    ├── SKILL.md              instructions for Claude
    ├── scripts/hu_eli.py     launcher: runs the bundled CLI, checks dependencies
    └── vendor/               filled by build_skill.py, not committed
        ├── VERSION           bundled commit and repository
        ├── pyproject.toml    entry point and dependency list are read from here
        ├── LICENSE
        └── src/hu_eli_mcp/   the package source, unchanged
```

**Build** (any OS, needs git and Python 3.11+), from a clone of this branch:

```bash
python skills/build_skill.py                  # bundles HEAD
python skills/build_skill.py --commit <rev>   # or a given commit, branch or tag
# -> dist/njt-jogszabalyok.zip
```

**Install:** on claude.ai, with code execution enabled under Settings > Capabilities,
upload the ZIP in the Skills section ("Upload skill"), or ship the folder in an
organization plugin. Keep a single copy: two skills named `njt-jogszabalyok` compete.

**In a chat** the skill starts with `scripts/hu_eli.py --selfcheck`. In a new sandbox it
reports the missing dependencies with the exact command, installed once from PyPI:

```
pip install --break-system-packages -q "fastmcp>=3.4,<4" "httpx>=0.27,<1" "diskcache>=5.6"
```

The launcher reads the entry point and the dependencies from the bundled `pyproject.toml`,
so it needs no change when the package changes. It also turns off the upstream runtime
manifest download (`HU_ELI_RUNTIME_URL=""`, see [Data and network](#data-and-network)).
SKILL.md names a fallback (an NJT proxy) only for when the bundled tool cannot run.

The dependencies are not bundled on purpose: with their own dependencies they come to about
66 MB including platform-specific binaries.

## Claude plugin

For Claude Code and the Claude desktop app; needs [uv](https://docs.astral.sh/uv/).

```
/plugin marketplace add danzig666/hu-eli-mcp#feat/local-decrees-plugin
/plugin install hu-eli-mcp@hu-eli-mcp
```

The plugin starts the MCP server with `uvx` from the source archive of one commit of this
fork; `plugin/uv.lock` pins that archive and every dependency with hashes. It ships the
`magyar-jogszabalyok` skill, which tells Claude which tool to use for which kind of
legislation. Details, what it sends and what it stores: [plugin/README.md](plugin/README.md).

## MCP server

The `hu-eli-mcp` package on PyPI is the upstream release, without municipal decrees and
paged text. Install this fork from its archive:

```bash
pip install "hu-eli-mcp @ https://github.com/danzig666/hu-eli-mcp/archive/refs/heads/feat/local-decrees-plugin.tar.gz"
```

Register it with your MCP client (see `.mcp.json.example`):

```json
{
  "mcpServers": {
    "hu-eli-mcp": {
      "command": "hu-eli-mcp",
      "env": {
        "HU_ELI_RUNTIME_URL": "",
        "HU_ELI_CACHE_DIR": "~/.matematic/cache/hu-eli",
        "HU_ELI_AUDIT_DIR": "~/.matematic/audit"
      }
    }
  }
}
```

### Tools

| Tool | What it does |
|---|---|
| `hu_read_local_decree(municipality, year, serial, date=None, start=0, max_chars=20000, search=None)` | A municipal decree's complete plain text in pages, with search. Annexes published only as files (plan sheets) are listed as PDF links. |
| `hu_get_local_decree(municipality, year, serial, date=None)` | Metadata of a municipal decree; `municipality` is a name or an issuer code. |
| `hu_find_municipality(name)` | ELI issuer code of a settlement, county or Budapest district from NJT's `/eli/kshkodok`, accent-insensitive: `Debrecen` → `735584`. Ambiguous names (Heves: town or county) return candidates. |
| `hu_read_text(doc_type, year, serial, issuer=None, date=None, start=0, max_chars=20000, search=None)` | The complete plain text of national legislation in pages, with search. Use this from a model client rather than `hu_get_text`. |
| `hu_get_act(year, serial)` | Metadata of an Act (törvény), e.g. `2013`, `5` (Civil Code). |
| `hu_get_legislation(doc_type, year, issuer, serial)` | Metadata of other legislation (decrees etc.); the issuer code is case-sensitive (`Korm`). |
| `hu_get_text(doc_type, year, serial, issuer=None)` | The complete NJT document HTML with deferred blocks restored; can be about 3 MB. |
| `hu_list_doc_types()` / `hu_list_issuers()` | Valid NJT document-type (`TV`, `R`, ...) and issuer codes. |
| `hu_coverage()` | What the connector covers and, explicitly, what it does not, each gap with a fallback. |

`date` takes `YYYY-MM-DD` (the version in force that day) or `kozlony` (as published).
`max_chars` is 1000 to 60000. Each page reports `next_start` while the document continues.

Every response carries the citation contract:

- `eli_uri`: the native ELI resolved, e.g. `https://njt.jog.gov.hu/eli/OR/2020/735584/47`;
- `human_readable_citation`: parsed from the document page, e.g. *"Debrecen Megyei Jogú
  Város Önkormányzata Közgyűlésének 47/2020 (XII.28.) önkormányzati rendelete (...)"*;
- `source_url`: the browsable `njt.jog.gov.hu/jogszabaly/...` page.

### Windows 11 with Smart App Control

Smart App Control blocks unsigned executables (`uvx.exe`, `pip.exe`, the `hu-eli-mcp.exe`
launcher). The python.org `python.exe` is signed, so go through the interpreter:

```bash
python -m pip install "hu-eli-mcp @ https://github.com/danzig666/hu-eli-mcp/archive/refs/heads/feat/local-decrees-plugin.tar.gz"
python -m hu_eli_mcp
```

```json
{ "mcpServers": { "hu-eli-mcp": { "command": "python", "args": ["-m", "hu_eli_mcp"] } } }
```

If `python` is not on PATH, use `py -3 -m hu_eli_mcp`. Do not turn Smart App Control off:
it cannot be re-enabled without reinstalling Windows.

## Command line

`hu-eli` is installed with the package (or run without installing:
`uvx --from https://github.com/danzig666/hu-eli-mcp/archive/refs/heads/feat/local-decrees-plugin.tar.gz hu-eli ...`).

```bash
hu-eli municipality Heves                                 # issuer codes, candidates if ambiguous
hu-eli local Debrecen 2020 47 --search "Lke-J/19"         # HÉSZ of Debrecen, hits with offsets
hu-eli local Debrecen 2020 47 --start 221000 --max-chars 6000
hu-eli local Debrecen 2020 47 --date 2023-01-01 --meta   # version in force that day, metadata only
hu-eli law TV 2023 100 --search "telepítési tanulmányterv" # 2023. évi C. tv. (Méptv.)
hu-eli law R 2021 Korm 419 --search "véleményezési szakasz"
```

Each text command prints a header (`citation`, `source_url`, `eli_uri`, `shown_in_force`,
`chars: A-B of N`, `next_start`, `matches`, attached annex files), then the text. Tables
print one row per line with `|` between cells. `--json` prints the raw tool result.

## What it does not do

- **No free-text search** (HU-001). NJT has no public search API; its search UI is a
  session-bound SPA. A document is addressed by its ELI coordinates; an unresolvable ELI
  surfaces as `not_found`.
- **No list of a municipality's decrees** (HU-004): NJT's list page
  `/eli/OR/{year}/{issuer}` returns a server error. Get the decree number from the NJT
  website or the municipality first.
- **File-only annexes are linked, not read** (HU-005), typically the plan sheets of a HÉSZ.
- **No case law** (HU-002) and **no judgement on legal force** (HU-003): text is returned
  as NJT publishes it for the requested date.

### NJT lazy-loads long laws and annexes

The ELI resolves, but the first server-rendered HTML can be incomplete: NJT fills
placeholder blocks through its undocumented frontend endpoint `POST /ajax/njtGetBlock.json`
while the browser scrolls (Criminal Code: 26 deferred blocks, Civil Code: 78, the Debrecen
HÉSZ: deferred annex content). The text tools restore these blocks in order and fail with
an upstream error if they cannot, rather than report a partial text as complete. The
endpoint is not a stable API and may need maintenance. Reproduction and payloads:
[docs/njt-deferred-content.md](docs/njt-deferred-content.md).

## Data and network

- **Read-only, public data.** Queries go to `njt.jog.gov.hu` only (document pages, ELI
  pages and the AJAX block endpoint above); no user text is uploaded. `robots.txt` is
  honoured (`/search/*` is never called).
- **Runtime manifest.** The upstream server fetches `hu-runtime.json.gz` (updated source
  addresses) from the upstream GitHub Releases on first use. `HU_ELI_RUNTIME_URL=""` turns
  it off; the plugin and the chat skill ship with it off and run on the built-in addresses.
- **Local files:** a response cache (`~/.matematic/cache/hu-eli`, `HU_ELI_CACHE_DIR`) and an
  audit log (`~/.matematic/audit/hu-eli-mcp.jsonl`, `HU_ELI_AUDIT_DIR`), one line per call
  with a SHA-256 hash of the input, not the input. `HU_ELI_BASE_URL` overrides the NJT host.
- **No fabrication.** ELI, title and citation are parsed from the resolved page; if NJT's
  markup changes, the tools fail loudly.

See `CONSTITUTION.md` (principles) and `DISCOVERY.md` (how the source was mapped, the
`njt.hu` → `njt.jog.gov.hu` domain and the issuer-code casing).

## Repository layout

```
src/hu_eli_mcp/        server (MCP tools), cli (hu-eli), client and lazy-load restore,
                       local (municipal ELI), textview (plain text, paging, search)
plugin/                Claude plugin: manifest, locked runtime, magyar-jogszabalyok skill
.claude-plugin/        marketplace entry pointing at plugin/
skills/                Claude chat skill and its ZIP builder
tests/                 offline gates; test_smoke.py calls live NJT
docs/                  NJT deferred-content investigation
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -k "not smoke"     # offline gates, as in CI (includes the skill ZIP build)
pytest tests/test_smoke.py       # live NJT
```

## Licence

Apache-2.0 ([LICENSE](LICENSE)). Original connector by Wieslaw Mazur / MateMatic
Solutions; municipal decrees, paged text, CLI, plugin packaging and chat skill in this fork
by danzig666. The Hungarian legislation served is official public data of Hungary; this
connector adds no rights over it.
