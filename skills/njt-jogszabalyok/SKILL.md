---
name: njt-jogszabalyok
description: Use when a question needs the text of Hungarian law - a törvény, kormányrendelet, miniszteri rendelet or an önkormányzati rendelet (HÉSZ, településképi rendelet, helyi adó) - or a citation to one. Reads it from njt.jog.gov.hu with the hu-eli command, in full and with the official source.
---

# Hungarian legislation from njt.jog.gov.hu (hu-eli command)

Answer from the official text, never from memory: wording, numbering and amendments change.
This skill runs the `hu-eli` command-line tool (from github.com/danzig666/hu-eli-mcp) in the
code execution environment. It needs network access to github.com, codeload.github.com,
pypi.org and njt.jog.gov.hu.

## Setup (once per conversation)

```bash
command -v hu-eli >/dev/null || pip install --break-system-packages -q \
  "hu-eli-mcp @ https://github.com/danzig666/hu-eli-mcp/archive/aac5b246bfb4259357d774f39114fac7152e4c96.tar.gz"
```

If the install or a lookup fails with a network error, tell the user that code execution
needs network access to those domains; do not answer from memory instead.

## Commands

```bash
# Municipal decree (önkormányzati rendelet), e.g. Debrecen HÉSZ = 47/2020. (XII. 28.)
hu-eli local Debrecen 2020 47 --search "Lke-J/19"
hu-eli local Debrecen 2020 47 --start 221000 --max-chars 6000   # read around a hit
hu-eli local Debrecen 2020 47 --date 2023-01-01                   # version in force that day
hu-eli municipality Heves          # issuer codes when a name is ambiguous (town vs county)
hu-eli local 729293 2020 1         # ...then use the numeric code

# National legislation
hu-eli law TV 1997 78 --search "telepítési tanulmányterv"   # Act: 1997. évi LXXVIII. tv. (Étv.)
hu-eli law R 2021 Korm 419 --search "véleményezési szakasz" # 419/2021. (VII. 15.) Korm. r.
hu-eli law R 2012 Korm 314 --start 40000                    # issuer codes are case-sensitive
```

Roman numerals in Act numbers are the serial in Arabic numerals (LXXVIII → 78). For other
national decree types the type and issuer codes are listed at
https://njt.jog.gov.hu/eli/tipuskodok and https://njt.jog.gov.hu/eli/kibocsatokodok.

## Reading the output

Each run prints a header, then the plain legal text (footnotes and page chrome removed):

- `citation`, `source_url`, `eli_uri`: cite these.
- `chars: A-B of N` and `next_start`: the text is paged (default 20,000 characters). If
  `next_start` is a number, the document continues: run again with `--start <that number>`.
  Never treat a first page as the whole document.
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
