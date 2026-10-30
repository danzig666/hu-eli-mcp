---
name: magyar-jogszabalyok
description: Use when a question needs the text of Hungarian law - a törvény, kormányrendelet, miniszteri rendelet or an önkormányzati rendelet (HÉSZ, településképi rendelet, helyi adó, közterület-használat) - or a citation to one. Reads it from njt.jog.gov.hu with the hu-eli-mcp tools, in full and with the official source.
---

# Hungarian legislation via the hu-eli-mcp tools

Answer from the official text on njt.jog.gov.hu, never from memory: wording, numbering and
amendments change, and a provision quoted from memory is a liability.

## Pick the tool

- **Municipal decree** (önkormányzati rendelet: HÉSZ, településképi rendelet, local tax, etc.)
  1. If the issuer is unclear or a name could mean several issuers (e.g. "Heves" is both the
     town and the county), call `hu_find_municipality` and use the numeric `code`.
  2. `hu_read_local_decree(municipality, year, serial, search=...)`.
     Example: Debrecen's HÉSZ, 47/2020. (XII. 28.) önkormányzati rendelet →
     `municipality="Debrecen", year="2020", serial="47"`.
- **Act** (törvény): `hu_read_text(doc_type="TV", year, serial, search=...)`.
  Example: Étv. = 1997. évi LXXVIII. törvény → `year="1997", serial="78"`.
- **Government or ministerial decree**: `hu_read_text(doc_type="R", year, serial,
  issuer="Korm")`. Issuer codes are case-sensitive; `hu_list_issuers` lists them.
  Example: 314/2012. (XI. 8.) Korm. rendelet → `year="2012", serial="314", issuer="Korm"`.
- Roman numerals in Act numbers are the serial in Arabic numerals (CXXX → 130).

## Reading a long document

The read tools return plain legal text in pages. Do not stop at the first page:

- To find a provision, pass `search` (case- and accent-insensitive, e.g. `"Lke-J/19"`,
  `"telepítési tanulmányterv"`, `"12. §"`). Each hit has a `start`; call again with
  `start` a few hundred characters before it and read the provision in context.
- To read everything, continue with `start=next_start` until `next_start` is null.
- `complete: false` means you have not seen the whole document. Before saying a rule or
  zone "does not exist", search for it.
- Zone tables (building zones and their parameters) appear as one row per line with `|`
  between cells; read the header rows above the hit to know which column is which.

## Versions

Text is the version in force today unless you pass `date="YYYY-MM-DD"` (the version in
force that day) or `date="kozlony"` (as originally published). For a planning or permit
question tied to a date (e.g. when an application was filed), read that date's version and
say which version you used.

## Annexes published as files

Municipal building regulations often publish the regulation plan sheets (szabályozási
terv) and other annexes only as files. They appear as `[PDF: url]` in the text and in
`attachments`. Their content is not in the text: give the user the link instead of
guessing what the plan shows.

## Citing

Cite with `human_readable_citation` and `source_url` from the result, plus the § / annex
you relied on, e.g. "Debrecen Megyei Jogú Város Önkormányzata Közgyűlésének 47/2020
(XII.28.) önkormányzati rendelete, 3. melléklet (https://njt.jog.gov.hu/jogszabaly/2020-47-SP-5Y1578)".
If a tool returns `not_found` or the question goes beyond the corpus, call `hu_coverage`
and say what is missing rather than answering from memory. There is no list of a
municipality's decrees: if the user does not know the decree number, ask for it or for
its title and year.
