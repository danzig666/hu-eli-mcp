"""Command-line access to the same tools, for use without an MCP client (e.g. a Claude skill).

    hu-eli municipality Debrecen
    hu-eli local Debrecen 2020 47 --search "Lke-J/19"
    hu-eli local Debrecen 2020 47 --start 120000 --max-chars 20000
    hu-eli local Ebes 2017 9 --date 2023-01-01 --meta
    hu-eli law TV 2012 100 --search garazdasag
    hu-eli law R 2012 Korm 314 --start 40000

Every text command prints a header with the official citation, the source URL and the
character range, then the text. When the header says ``next_start: N`` the document
continues: run the same command with ``--start N``. ``--json`` prints the raw tool result.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .server import (
    ToolError,
    hu_find_municipality,
    hu_get_local_decree,
    hu_read_local_decree,
    hu_read_text,
)


def _print_page(result, as_json: bool) -> None:
    if as_json:
        print(result.model_dump_json(indent=2))
        return
    lines = [
        f"citation: {result.human_readable_citation}",
        f"source_url: {result.source_url}",
        f"eli_uri: {result.eli_uri}",
    ]
    if getattr(result, "issuer_name", None):
        lines.append(f"issuer: {result.issuer} = {result.issuer_name}")
    if result.date:
        lines.append(f"version: {result.date}")
    if result.in_force_date:
        lines.append(f"shown_in_force: {result.in_force_date}")
    lines.append(
        f"chars: {result.start}-{result.end} of {result.total_chars}"
        + (" (complete)" if result.complete else "")
    )
    lines.append(
        f"next_start: {result.next_start}" if result.next_start is not None
        else "next_start: none (end of document)"
    )
    if result.matches:
        lines.append(f"matches ({len(result.matches)}, offset: snippet):")
        lines += [f"  {m.start}: {m.snippet}" for m in result.matches]
    if result.attachments:
        lines.append("attached annex files (content not in the text):")
        lines += [f"  {a.title} -> {a.url}" for a in result.attachments]
    print("\n".join(lines))
    print("-" * 72)
    print(result.text)


async def _run(args: argparse.Namespace) -> int:
    if args.command == "municipality":
        result = await hu_find_municipality(args.name, limit=args.limit)
        if args.json:
            print(result.model_dump_json(indent=2))
        elif not result.items:
            print(f"No issuer matches {args.name!r}.")
        else:
            for item in result.items:
                print(f"{item.code}\t{item.name}")
        return 0

    if args.command == "local":
        if args.meta:
            meta = await hu_get_local_decree(
                args.municipality, args.year, args.serial, date=args.date, doc_type=args.type
            )
            print(meta.model_dump_json(indent=2, exclude={"dataset_note"}))
            return 0
        result = await hu_read_local_decree(
            args.municipality, args.year, args.serial, date=args.date, start=args.start,
            max_chars=args.max_chars, search=args.search, doc_type=args.type,
        )
    else:
        result = await hu_read_text(
            args.doc_type, args.year, args.serial, issuer=args.issuer, date=args.date,
            start=args.start, max_chars=args.max_chars, search=args.search,
        )
    if args.search and not result.matches and not args.json:
        print(f"search: no match for {args.search!r}")
    _print_page(result, args.json)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hu-eli", description="Hungarian legislation from njt.jog.gov.hu by ELI."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    muni = sub.add_parser("municipality", help="find a local government's ELI issuer code")
    muni.add_argument("name")
    muni.add_argument("--limit", type=int, default=10)
    muni.add_argument("--json", action="store_true")

    def paging(p: argparse.ArgumentParser) -> None:
        p.add_argument("--date", help="YYYY-MM-DD (version in force that day) or 'kozlony'")
        p.add_argument("--start", type=int, default=0)
        p.add_argument("--max-chars", type=int, default=20000)
        p.add_argument("--search", help="phrase to locate (case/accent-insensitive)")
        p.add_argument("--json", action="store_true")

    local = sub.add_parser("local", help="read a municipal decree (onkormanyzati rendelet)")
    local.add_argument("municipality", help="name (e.g. Debrecen) or numeric issuer code")
    local.add_argument("year")
    local.add_argument("serial")
    local.add_argument("--type", default="OR", help="OR (decree, default) or RI (justification)")
    local.add_argument("--meta", action="store_true", help="metadata only, no text")
    paging(local)

    law = sub.add_parser("law", help="read national legislation")
    law.add_argument("doc_type", help="e.g. TV (Act), R (decree); see NJT /eli/tipuskodok")
    law.add_argument("year")
    law.add_argument("rest", nargs="+", help="SERIAL for TV, otherwise ISSUER SERIAL")
    paging(law)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "law":
        if args.doc_type == "TV":
            if len(args.rest) != 1:
                print("usage: hu-eli law TV YEAR SERIAL", file=sys.stderr)
                return 2
            args.issuer, args.serial = None, args.rest[0]
        else:
            if len(args.rest) != 2:
                print("usage: hu-eli law TYPE YEAR ISSUER SERIAL", file=sys.stderr)
                return 2
            args.issuer, args.serial = args.rest
    try:
        return asyncio.run(_run(args))
    except ToolError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # surface upstream problems as one readable line
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
