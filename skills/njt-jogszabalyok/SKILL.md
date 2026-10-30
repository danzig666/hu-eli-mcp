---
name: "njt-jogszabalyok"
description: "Use when a question needs the text of Hungarian law (törvény, Korm. rendelet, önkormányzati rendelet such as a HÉSZ) or a citation to one; reads it in full from njt.jog.gov.hu."
---

# Hungarian legislation from njt.jog.gov.hu (bundled hu-eli tool)

Answer from the official text, never from memory: wording, numbering and amendments change.

The `hu-eli` command-line tool (danzig666/hu-eli-mcp, the commit recorded in
`vendor/VERSION`) is **bundled in this skill folder**. Run the bundled copy through
`scripts/hu_eli.py`. Do not download, clone or pip-install hu-eli-mcp from GitHub: the
bundled copy is the version the user approved. The tool needs network access to
njt.jog.gov.hu, and to pypi.org only if a dependency is missing.

## Setup (once per conversation)

Shell state does not persist between Bash calls, so put the launcher path in a variable at
the start of every command. Use the base directory printed when this skill was loaded:

```bash
H="python3 /mnt/skills/plugins/njt-jogszabalyok/scripts/hu_eli.py"
$H --selfcheck
```

`--selfcheck` prints `OK` when everything is in place. If it lists missing dependencies, it
prints the exact install command: those are package names from the bundled
`vendor/pyproject.toml`, installed from PyPI only. Run that command once, then continue.
Never install anything from a GitHub URL.

## Commands

```bash
H="python3 /mnt/skills/plugins/njt-jogszabalyok/scripts/hu_eli.py"

# Municipal decree (önkormányzati rendelet), e.g. Debrecen HÉSZ = 47/2020. (XII. 28.)
$H local Debrecen 2020 47 --search "Lke-J/19"
$H local Debrecen 2020 47 --start 221000 --max-chars 6000   # read around a hit
$H local Debrecen 2020 47 --date 2023-01-01                   # version in force that day
$H municipality Heves          # issuer codes when a name is ambiguous (town vs county)
$H local 729293 2020 1         # ...then use the numeric code

# National legislation
$H law TV 2023 100 --search "telepítési tanulmányterv"  # Act: 2023. évi C. tv. (Méptv.)
$H law R 2021 Korm 419 --search "véleményezési szakasz" # 419/2021. (VII. 15.) Korm. r.
$H law R 2012 Korm 314 --start 40000                    # issuer codes are case-sensitive
```

Roman numerals in Act numbers are the serial in Arabic numerals (C → 100). For other
national decree types the type and issuer codes are listed at
https://njt.jog.gov.hu/eli/tipuskodok and https://njt.jog.gov.hu/eli/kibocsatokodok.

## Fallback: the user's NJT proxy

Use this only if the bundled tool cannot run (missing files, a dependency that cannot be
installed, or njt.jog.gov.hu unreachable from the shell). It needs no installation. Save
the output to a file and search it with grep, do not page it through the conversation.

```bash
P='https://t4terv.hu/njt_proxy.php?url=https://njt.jog.gov.hu/jogszabaly/2020-47-SP-5Y1578'
curl -sS -m 60 "$P&toc=1"                    # structure, with the {par=…}/{mell=…} to request
curl -sS -m 60 "$P&par=54-56&format=text"    # sections (range includes lettered ones, e.g. 55/A)
curl -sS -m 60 "$P&par=55&bek=3&format=text" # one paragraph of one section
curl -sS -m 60 "$P&mell=2&format=text"       # annex; tables one row per line, | separated
```

The NJT address comes from the decree's page (`jogszabaly/<year>-<number>-SP-<issuer>` for
municipal decrees, e.g. `2020-47-SP-5Y1578`; `1997-78-00-00` for an Act). If you only have
the ELI data, get the address with the bundled tool first. Errors are plain text: 404 when
the section does not exist in that version, 400 for an unreadable parameter. Say in the
answer that the text came through the proxy.

## Reading the output

Each run prints a header, then the plain legal text (footnotes and page chrome removed):

- `citation`, `source_url`, `eli_uri`: cite these.
- `chars: A-B of N` and `next_start`: the text is paged (default 20,000 characters). If
  `next_start` is a number, the document continues: run again with `--start <that number>`.
  Never treat a first page as the whole document. `--max-chars` accepts 1000 to 60000.
- `matches`: with `--search` (case- and accent-insensitive), every hit as `offset: snippet`.
  Read a hit in context with `--start <offset minus a few hundred> --max-chars 6000`.
  Before telling the user a rule, zone or section does not exist, search for it.
- Tables (e.g. building zone parameters) print one row per line with `|` between cells; read
  the header rows above a hit to know the columns.
- `attached annex files`: annexes published only as files, typically the regulation plan
  sheets of a HÉSZ, with their PDF links. Their content is not in the text; give the user the
  link rather than guessing what a plan shows.

Errors: `[not_found]` means NJT has no document at that address (check year, number,
issuer); `[invalid_arg]` explains the problem, and for an ambiguous municipality lists the
candidates with their codes. There is no list of a municipality's decrees: if the user does
not know the decree number, ask for it or for its title and year.

## Answering

- Quote or paraphrase only what you read, with the § / point / annex reference.
- Cite as the `citation` line plus the § and the `source_url`, e.g. "Debrecen Megyei Jogú
  Város Önkormányzata Közgyűlésének 47/2020 (XII.28.) önkormányzati rendelete, 3. melléklet
  (https://njt.jog.gov.hu/jogszabaly/2020-47-SP-5Y1578)".
- The default is the version in force today. When the question is tied to a date (an
  application filed, a plan adopted), read that date's version with `--date` and say which
  version you used.
