"""FastMCP entry point - Hungarian national legislation (Nemzeti Jogszabalytar) tools.

Run:

    python -m hu_eli_mcp.server

Configuration via env:

- ``HU_ELI_CACHE_DIR`` (default ``~/.matematic/cache/hu-eli``)
- ``HU_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
- ``HU_ELI_BASE_URL`` (default ``https://njt.jog.gov.hu``)
"""

from __future__ import annotations

import os
import re

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import runtime
from .audit import AuditLogger, hash_input, timer
from .citations import human_readable_citation, parse_code_table, parse_document_page
from .client import DEFAULT_BASE_URL, HuError, HuNotFoundError, NjtClient
from .coverage import Coverage, build_coverage
from .local import (
    DATE_RE,
    LOCAL_DOC_TYPES,
    AmbiguousMunicipalityError,
    Municipality,
    resolve_municipality,
    search_municipalities,
)
from .models import (
    AttachmentInfo,
    DocTypeInfo,
    DocTypeList,
    IssuerInfo,
    IssuerList,
    Legislation,
    LegislationText,
    MunicipalityInfo,
    MunicipalityList,
    TextMatch,
    TextPage,
)
from .textview import extract, page, search_text

INSTRUCTIONS = """\
This MCP server exposes Hungary's official national legislation database, the Nemzeti Jogszabalytar (NJT, njt.jog.gov.hu), maintained by MKIFK. It has no documented public REST/JSON API - the search/browse UI is a JavaScript SPA that requires a session and is not usable headlessly. Instead, this server resolves Hungary's genuine, documented national ELI (European Legislation Identifier) URI scheme (published since 2023, see njt.jog.gov.hu/eli/urisemak) and fetches the resulting server-rendered document page. Every response carries a stable `eli_uri` (a real, native ELI - never fabricated), a `human_readable_citation` and a `source_url` (the citation contract).

## No free-text search

There is no headless full-text or title search. Documents must be addressed by a **known ELI**: a document type code, a year, a serial number, and (for everything except Acts) an issuer code. Use `hu_list_doc_types` and `hu_list_issuers` to discover valid codes; use `hu_get_act` for Acts (torveny) which need no issuer code, or `hu_get_legislation` for any other document type (government/ministerial decrees, etc.) which do.

## ELI shape

- Acts (torveny): `hu_get_act(year, serial)` -> ELI `/eli/TV/{year}/{serial}`.
- Everything else: `hu_get_legislation(doc_type, year, issuer, serial)` -> ELI `/eli/{doc_type}/{year}/{issuer}/{serial}`. **The issuer code is case-sensitive** (e.g. `Korm` for Government decrees, not `KORM` - use `hu_list_issuers` to get the exact casing).
- `hu_get_text` fetches complete document HTML, including deferred sections and annexes loaded via NJT's internal AJAX endpoint. Do not assume an ELI redirect or large initial HTML is complete.
- Municipal decrees (onkormanyzati rendeletek): `hu_get_local_decree(municipality, year, serial)` -> ELI `/eli/OR/{year}/{issuer code}/{serial}`. `municipality` is a name (e.g. "Debrecen") or the numeric issuer code from `hu_find_municipality`; an ambiguous name is rejected with candidates, never guessed.
- Reading text: prefer `hu_read_text` (national) and `hu_read_local_decree` (municipal). They return the complete plain legal text in pages (`start`, `max_chars`, continue with `next_start` until it is null) and can `search` for a phrase, returning each hit's offset. `hu_get_text` returns raw HTML of 1-3 MB, which most clients truncate.
- Point in time: the read tools and `hu_get_local_decree` accept `date` = `YYYY-MM-DD` (the version in force that day) or `kozlony` (as published).

## Call order

1. `hu_list_doc_types` / `hu_list_issuers` - discover valid type/issuer codes if unknown.
2. `hu_get_act(year, serial)` or `hu_get_legislation(doc_type, year, issuer, serial)` - metadata: `eli_uri`, `title`, `subtitle`, `in_force_date`, `human_readable_citation`, `source_url`.
3. `hu_get_text(...)` - complete HTML, reconstructing lazy-loaded NJT content where needed.
4. Municipal: `hu_find_municipality` if the issuer is unclear, then `hu_get_local_decree` / `hu_read_local_decree`.

## Reading long documents

- A page with `complete: false` is not the whole document. Before stating that a provision does not exist, `search` for it or read on with `next_start`.
- Municipal building regulations often publish annexes (plan sheets) only as files: the text shows `[PDF: url]` and `attachments` lists them. Their content is not in the text; give the user the link.

## Hard constraints

- **Do not answer past the edge of this corpus** - when a search comes back empty, or the question touches material this connector does not carry, call `hu_coverage` and relay what it says is missing. Absence here is not absence in the law.
- **eli_uri is a genuine native ELI** - Hungary has published a documented ELI implementation since 2023; this server never constructs a substitute identifier.
- **No free-text search** - only get-by-known-identifier. An unresolvable identifier (wrong year/serial/issuer/casing) makes NJT redirect to its own search-assist page; this server surfaces that as `not_found` rather than guessing.
- **Consolidated ("hatalyos") text by default** - the resolved document is the version currently in force; `in_force_date` (if present on the page) states the as-of date NJT itself displays.
- **Every response has `human_readable_citation` + `source_url`** - cite both to the user.
- **No modification of official text** - returned verbatim from njt.jog.gov.hu.
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/hu-eli-mcp.jsonl`.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing or malformed (e.g. a non-numeric year/serial).
- `not_found` - NJT could not resolve the ELI (redirected to its search-assist page) or the document page 404s.
- `upstream_error` - an NJT HTTP error (timeout, 5xx, transport failure). Retry once before surfacing.

## Response style

- Cite legislation as `human_readable_citation` with the `source_url`: "2013. evi V. torveny (a Polgari Torvenykonyvrol), https://njt.jog.gov.hu/jogszabaly/2013-5-00-00".
- NEVER invent a doc_type code, an issuer code, a title or an ELI - take each from the tool output or from `hu_list_doc_types` / `hu_list_issuers`.
"""

_YEAR_RE = re.compile(r"^\d{4}$")
_SERIAL_RE = re.compile(r"^[A-Za-z0-9./-]+$")
_CODE_RE = re.compile(r"^[A-Za-z_]+$")


class ToolError(Exception):
    """Structured error for hu-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({"invalid_arg", "not_found", "upstream_error"})

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

mcp: FastMCP = FastMCP(name="hu-eli-mcp", instructions=INSTRUCTIONS)


def _base_url() -> str:
    return os.environ.get("HU_ELI_BASE_URL", runtime.base_url("eli", DEFAULT_BASE_URL)).rstrip("/")


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, HuNotFoundError):
        return ToolError("not_found", str(exc))
    if isinstance(exc, HuError):
        return ToolError("upstream_error", str(exc))
    import httpx

    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return ToolError("not_found", "NJT returned 404 for this document.")
    if isinstance(exc, (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"NJT error: {type(exc).__name__}: {exc}")
    return exc


def _check_year(year: str) -> str:
    cleaned = str(year).strip()
    if not _YEAR_RE.match(cleaned):
        raise ToolError("invalid_arg", f"year={year!r} must be a 4-digit year, e.g. '2013'.")
    return cleaned


def _check_serial(serial: str) -> str:
    cleaned = str(serial).strip()
    if not cleaned or not _SERIAL_RE.match(cleaned):
        raise ToolError("invalid_arg", f"serial={serial!r} must be a non-empty NJT serial number.")
    return cleaned


def _check_code(label: str, code: str) -> str:
    cleaned = str(code).strip()
    if not cleaned or not _CODE_RE.match(cleaned):
        raise ToolError("invalid_arg", f"{label}={code!r} must be a non-empty NJT code (letters only).")
    return cleaned


def _to_legislation(
    *, doc_type: str, year: str, serial: str, issuer: str | None, eli_path: str,
    source_url: str, parsed: dict[str, str],
) -> Legislation:
    return Legislation(
        doc_type=doc_type,
        year=year,
        serial=serial,
        issuer=issuer,
        title=parsed.get("title"),
        subtitle=parsed.get("subtitle"),
        in_force_date=parsed.get("in_force_date"),
        eli_uri=f"{_base_url()}{eli_path}",
        human_readable_citation=human_readable_citation(parsed.get("title"), parsed.get("subtitle")),
        source_url=source_url,
    )


# ---------------------------------------------------------------------------
# hu_get_act
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def hu_get_act(year: str, serial: str) -> Legislation:
    """Fetch metadata for a Hungarian Act (torveny) by its ELI (year + serial).

    Args:
        year: 4-digit year, e.g. ``"2013"``.
        serial: the Act's serial number within that year, e.g. ``"5"`` (2013. evi V. torveny
            is Act no. 5 of 2013, the Hungarian Civil Code).

    Returns:
        ``Legislation`` with ``eli_uri``, ``title``, ``subtitle``, ``human_readable_citation``,
        ``source_url``.
    """
    audit = _audit()
    y = _check_year(year)
    s = _check_serial(serial)
    eli_path = f"/eli/TV/{y}/{s}"
    input_hash = hash_input({"tool": "hu_get_act", "year": y, "serial": s})

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                source_url, html = await client.resolve_eli(eli_path)
        except Exception as exc:
            audit.log(tool="hu_get_act", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    parsed = parse_document_page(html)
    result = _to_legislation(
        doc_type="TV", year=y, serial=s, issuer=None, eli_path=eli_path,
        source_url=source_url, parsed=parsed,
    )
    audit.log(tool="hu_get_act", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# hu_get_legislation
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def hu_get_legislation(doc_type: str, year: str, issuer: str, serial: str) -> Legislation:
    """Fetch metadata for any Hungarian legislation by its ELI (type + year + issuer + serial).

    Use this for anything other than Acts (torveny) - government decrees, ministerial decrees,
    etc. Use `hu_list_doc_types` for valid `doc_type` codes and `hu_list_issuers` for valid
    `issuer` codes (issuer codes are case-sensitive, e.g. `Korm` for Government).

    Args:
        doc_type: NJT type code, e.g. ``"R"`` (rendelet / decree).
        year: 4-digit year, e.g. ``"2016"``.
        issuer: NJT issuer code, case-sensitive, e.g. ``"Korm"`` (Government).
        serial: the document's serial number within that year, e.g. ``"428"``.

    Returns:
        ``Legislation`` with ``eli_uri``, ``title``, ``subtitle``, ``human_readable_citation``,
        ``source_url``.
    """
    audit = _audit()
    dt = _check_code("doc_type", doc_type)
    y = _check_year(year)
    iss = _check_code("issuer", issuer)
    s = _check_serial(serial)
    eli_path = f"/eli/{dt}/{y}/{iss}/{s}"
    input_hash = hash_input(
        {"tool": "hu_get_legislation", "doc_type": dt, "year": y, "issuer": iss, "serial": s}
    )

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                source_url, html = await client.resolve_eli(eli_path)
        except Exception as exc:
            audit.log(tool="hu_get_legislation", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    parsed = parse_document_page(html)
    result = _to_legislation(
        doc_type=dt, year=y, serial=s, issuer=iss, eli_path=eli_path,
        source_url=source_url, parsed=parsed,
    )
    audit.log(tool="hu_get_legislation", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# hu_get_text
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def hu_get_text(
    doc_type: str, year: str, serial: str, issuer: str | None = None
) -> LegislationText:
    """Fetch complete legislation HTML, including NJT's deferred blocks.

    The result can be very large (the Civil Code is about 3 MB of HTML). Check
    `byte_size`: if your client truncates tool results, the text you see is not the
    whole law, so do not conclude that a section is absent from what you received.

    For Acts (torveny), pass `doc_type="TV"` and omit `issuer`. For anything else, pass the
    `issuer` code (case-sensitive - use `hu_list_issuers`).

    Args:
        doc_type: NJT type code, e.g. ``"TV"`` (torveny / Act) or ``"R"`` (rendelet / decree).
        year: 4-digit year.
        serial: the document's serial number within that year.
        issuer: NJT issuer code, case-sensitive (required for everything except `"TV"`).

    Returns:
        ``LegislationText`` with the citation contract and ``content`` (the document's HTML).
    """
    audit = _audit()
    dt = _check_code("doc_type", doc_type)
    y = _check_year(year)
    s = _check_serial(serial)
    if dt == "TV":
        eli_path = f"/eli/TV/{y}/{s}"
        iss: str | None = None
    else:
        if not issuer:
            raise ToolError("invalid_arg", "issuer is required for doc_type other than 'TV'.")
        iss = _check_code("issuer", issuer)
        eli_path = f"/eli/{dt}/{y}/{iss}/{s}"
    input_hash = hash_input(
        {"tool": "hu_get_text", "doc_type": dt, "year": y, "issuer": iss, "serial": s}
    )

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                source_url, html = await client.resolve_eli(eli_path)
                html = await client.load_complete_text(source_url, html)
        except Exception as exc:
            audit.log(tool="hu_get_text", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    parsed = parse_document_page(html)
    result = LegislationText(
        doc_type=dt,
        year=y,
        serial=s,
        issuer=iss,
        title=parsed.get("title"),
        subtitle=parsed.get("subtitle"),
        in_force_date=parsed.get("in_force_date"),
        eli_uri=f"{_base_url()}{eli_path}",
        human_readable_citation=human_readable_citation(parsed.get("title"), parsed.get("subtitle")),
        source_url=source_url,
        content=html,
        byte_size=len(html.encode("utf-8")),
    )
    audit.log(tool="hu_get_text", input_hash=input_hash, output_count_or_size=result.byte_size or 0,
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# hu_list_doc_types
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def hu_list_doc_types() -> DocTypeList:
    """List valid NJT document-type codes (e.g. TV=Act, R=decree) from /eli/tipuskodok.

    Returns:
        ``DocTypeList`` with ``items: list[DocTypeInfo]`` (code + Hungarian name).
    """
    audit = _audit()
    input_hash = hash_input({"tool": "hu_list_doc_types"})

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                html = await client.get_code_list("/eli/tipuskodok")
        except Exception as exc:
            audit.log(tool="hu_list_doc_types", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    rows = parse_code_table(html)
    items = [DocTypeInfo(code=code, name=name or None) for code, name in rows]
    result = DocTypeList(items=items)
    audit.log(tool="hu_list_doc_types", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# hu_list_issuers
@mcp.tool(annotations=READ_ONLY)
async def hu_coverage() -> Coverage:
    """Declare what this connector covers, how it is sourced, and what it does NOT cover.

    Call this before telling a user that the law "does not contain" something, and whenever
    a search comes back empty: the absence may be a gap in this connector rather than in the
    law. Every gap carries a fallback saying where to look instead.

    Returns:
        ``Coverage`` with families, an as-of note, and a non-empty list of known gaps.
    """
    audit = _audit()
    input_hash = hash_input({})

    with timer() as t:
        coverage = build_coverage()

    audit.log(
        tool="hu_coverage",
        input_hash=input_hash,
        output_count_or_size=len(coverage.known_gaps),
        duration_ms=t.duration_ms,
        status="ok",
    )
    return coverage


# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def hu_list_issuers() -> IssuerList:
    """List valid NJT issuer codes (case-sensitive, e.g. Korm=Government) from /eli/kibocsatokodok.

    Returns:
        ``IssuerList`` with ``items: list[IssuerInfo]`` (code + Hungarian name).
    """
    audit = _audit()
    input_hash = hash_input({"tool": "hu_list_issuers"})

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                html = await client.get_code_list("/eli/kibocsatokodok")
        except Exception as exc:
            audit.log(tool="hu_list_issuers", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    rows = parse_code_table(html)
    items = [IssuerInfo(code=code, name=name or None) for code, name in rows if code]
    result = IssuerList(items=items)
    audit.log(tool="hu_list_issuers", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return result



# ---------------------------------------------------------------------------
# Municipal decrees and paged plain-text reading
# ---------------------------------------------------------------------------

_DEFAULT_PAGE = 20_000
_MAX_PAGE = 60_000


def _check_date(date: str | None) -> str | None:
    if date is None or not str(date).strip():
        return None
    cleaned = str(date).strip()
    if not DATE_RE.match(cleaned):
        raise ToolError(
            "invalid_arg",
            f"date={date!r} must be YYYY-MM-DD (the version in force that day) or 'kozlony' "
            "(the version as originally published).",
        )
    return cleaned


def _check_local_type(doc_type: str) -> str:
    cleaned = str(doc_type).strip().upper()
    if cleaned not in LOCAL_DOC_TYPES:
        raise ToolError(
            "invalid_arg",
            f"doc_type={doc_type!r} must be one of {sorted(LOCAL_DOC_TYPES)} "
            "(OR = municipal decree, RI = its justification).",
        )
    return cleaned


def _check_paging(start: int, max_chars: int) -> tuple[int, int]:
    try:
        st, mx = int(start), int(max_chars)
    except (TypeError, ValueError):
        raise ToolError("invalid_arg", "start and max_chars must be integers.") from None
    if st < 0:
        raise ToolError("invalid_arg", f"start={start!r} must be >= 0.")
    if not 1_000 <= mx <= _MAX_PAGE:
        raise ToolError("invalid_arg", f"max_chars={max_chars!r} must be 1000..{_MAX_PAGE}.")
    return st, mx


async def _municipality(client: NjtClient, query: str) -> Municipality:
    rows = parse_code_table(await client.get_code_list("/eli/kshkodok"))
    if not rows:
        raise HuError("NJT's /eli/kshkodok code list could not be parsed.")
    try:
        return resolve_municipality(rows, query)
    except AmbiguousMunicipalityError as exc:
        raise ToolError("invalid_arg", str(exc)) from exc
    except LookupError as exc:
        raise ToolError("not_found", str(exc)) from exc


def _text_page(
    *, doc_type: str, year: str, serial: str, issuer: str | None, issuer_name: str | None,
    date: str | None, eli_path: str, source_url: str, html: str, start: int,
    max_chars: int, search: str | None,
) -> TextPage:
    parsed = parse_document_page(html)
    text, attachments = extract(html, _base_url())
    chunk, end, next_start = page(text, start, max_chars)
    matches = search_text(text, search) if search and search.strip() else []
    return TextPage(
        doc_type=doc_type, year=year, serial=serial, issuer=issuer, issuer_name=issuer_name,
        date=date, title=parsed.get("title"), subtitle=parsed.get("subtitle"),
        in_force_date=parsed.get("in_force_date"), eli_uri=f"{_base_url()}{eli_path}",
        human_readable_citation=human_readable_citation(parsed.get("title"), parsed.get("subtitle")),
        source_url=source_url, start=min(start, len(text)), end=end, total_chars=len(text),
        next_start=next_start, complete=start == 0 and next_start is None, text=chunk,
        matches=[TextMatch(**m) for m in matches],
        attachments=[AttachmentInfo(**a) for a in attachments],
    )


@mcp.tool(annotations=READ_ONLY)
async def hu_find_municipality(name: str, limit: int = 10) -> MunicipalityList:
    """Find the ELI issuer code of a local government (settlement, county or Budapest district).

    Searches NJT's /eli/kshkodok table, accent- and case-insensitively, best match first.
    Use the returned `code` (e.g. ``"735584"`` for Debrecen) with `hu_get_local_decree` and
    `hu_read_local_decree` when a name is ambiguous.

    Args:
        name: (part of) the name, e.g. ``"Debrecen"``, ``"Hajdu-Bihar"``, ``"Budapest XI"``,
            or a numeric code to look up its name.
        limit: maximum number of results (1-50).
    """
    audit = _audit()
    q = str(name).strip()
    if not q:
        raise ToolError("invalid_arg", "name must not be empty.")
    lim = max(1, min(int(limit), 50))
    input_hash = hash_input({"tool": "hu_find_municipality", "name": q, "limit": lim})

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                html = await client.get_code_list("/eli/kshkodok")
        except Exception as exc:
            audit.log(tool="hu_find_municipality", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    found = search_municipalities(parse_code_table(html), q, limit=lim)
    result = MunicipalityList(
        query=q, items=[MunicipalityInfo(code=m.code, name=m.name) for m in found]
    )
    audit.log(tool="hu_find_municipality", input_hash=input_hash,
              output_count_or_size=len(result.items), duration_ms=t.duration_ms, status="ok")
    return result


@mcp.tool(annotations=READ_ONLY)
async def hu_get_local_decree(
    municipality: str, year: str, serial: str, date: str | None = None, doc_type: str = "OR"
) -> Legislation:
    """Fetch metadata for a municipal decree (onkormanyzati rendelet) by its ELI.

    ELI: ``/eli/OR/{year}/{issuer code}/{serial}[/{date}]``. Example: Debrecen's local building
    regulation, 47/2020. (XII. 28.) onkormanyzati rendelet, is
    ``municipality="Debrecen", year="2020", serial="47"``.

    Args:
        municipality: the issuing local government's name (e.g. ``"Ebes"``) or its numeric
            code from `hu_find_municipality`. An ambiguous name is rejected with candidates.
        year: 4-digit year of the decree.
        serial: the decree's number within that year.
        date: optional ``YYYY-MM-DD`` for the version in force that day, or ``"kozlony"``
            for the version as published; omit for the version in force now.
        doc_type: ``"OR"`` (the decree, default) or ``"RI"`` (its justification).
    """
    audit = _audit()
    dt = _check_local_type(doc_type)
    y = _check_year(year)
    s = _check_serial(serial)
    d = _check_date(date)
    input_hash = hash_input({"tool": "hu_get_local_decree", "municipality": str(municipality),
                             "year": y, "serial": s, "date": d, "doc_type": dt})

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                muni = await _municipality(client, str(municipality))
                eli_path = f"/eli/{dt}/{y}/{muni.code}/{s}" + (f"/{d}" if d else "")
                source_url, html = await client.resolve_eli(eli_path)
        except Exception as exc:
            audit.log(tool="hu_get_local_decree", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            if isinstance(exc, ToolError):
                raise
            raise _map_upstream(exc) from exc

    result = _to_legislation(
        doc_type=dt, year=y, serial=s, issuer=muni.code, eli_path=eli_path,
        source_url=source_url, parsed=parse_document_page(html),
    )
    result.issuer_name = muni.name  # type: ignore[attr-defined]
    result.date = d  # type: ignore[attr-defined]
    audit.log(tool="hu_get_local_decree", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return result


@mcp.tool(annotations=READ_ONLY)
async def hu_read_local_decree(
    municipality: str,
    year: str,
    serial: str,
    date: str | None = None,
    start: int = 0,
    max_chars: int = _DEFAULT_PAGE,
    search: str | None = None,
    doc_type: str = "OR",
) -> TextPage:
    """Read a municipal decree's complete plain text, one page at a time, with search.

    The whole decree is loaded (including NJT's lazy-loaded sections and annexes), converted
    to plain legal text, and returned from `start` for up to `max_chars` characters. Continue
    with `start=next_start` until `next_start` is null; `complete` is true only when one page
    holds the whole text. With `search` (case- and accent-insensitive), `matches` lists every
    hit's offset and snippet - read from a hit's `start` to see the provision in context.
    Annexes published only as files (e.g. plan sheets of a building regulation) appear as
    ``[PDF: url]`` in the text and in `attachments`.

    Args:
        municipality: issuer name (e.g. ``"Debrecen"``) or numeric code.
        year: 4-digit year of the decree.
        serial: the decree's number within that year.
        date: optional ``YYYY-MM-DD`` (version in force that day) or ``"kozlony"``.
        start: character offset to read from (0 = beginning).
        max_chars: page size, 1000-60000 (default 20000).
        search: optional phrase to locate, e.g. ``"Lke-J/19"`` or ``"telepulesi foepitesz"``.
        doc_type: ``"OR"`` (default) or ``"RI"`` (justification).
    """
    audit = _audit()
    dt = _check_local_type(doc_type)
    y = _check_year(year)
    s = _check_serial(serial)
    d = _check_date(date)
    st, mx = _check_paging(start, max_chars)
    input_hash = hash_input({"tool": "hu_read_local_decree", "municipality": str(municipality),
                             "year": y, "serial": s, "date": d, "doc_type": dt,
                             "start": st, "max_chars": mx, "search": search})

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                muni = await _municipality(client, str(municipality))
                eli_path = f"/eli/{dt}/{y}/{muni.code}/{s}" + (f"/{d}" if d else "")
                source_url, html = await client.resolve_eli(eli_path)
                html = await client.load_complete_text(source_url, html)
        except Exception as exc:
            audit.log(tool="hu_read_local_decree", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            if isinstance(exc, ToolError):
                raise
            raise _map_upstream(exc) from exc

    result = _text_page(
        doc_type=dt, year=y, serial=s, issuer=muni.code, issuer_name=muni.name, date=d,
        eli_path=eli_path, source_url=source_url, html=html, start=st, max_chars=mx,
        search=search,
    )
    audit.log(tool="hu_read_local_decree", input_hash=input_hash,
              output_count_or_size=len(result.text), duration_ms=t.duration_ms, status="ok")
    return result


@mcp.tool(annotations=READ_ONLY)
async def hu_read_text(
    doc_type: str,
    year: str,
    serial: str,
    issuer: str | None = None,
    date: str | None = None,
    start: int = 0,
    max_chars: int = _DEFAULT_PAGE,
    search: str | None = None,
) -> TextPage:
    """Read national legislation's complete plain text, one page at a time, with search.

    Same addressing as `hu_get_text` (Acts: ``doc_type="TV"``, no issuer), but returns plain
    legal text in pages instead of megabytes of HTML, so long codes (Btk., Ptk.) can be read
    in full. Continue with `start=next_start` until `next_start` is null. With `search`,
    `matches` gives each hit's offset and snippet.

    Args:
        doc_type: NJT type code, e.g. ``"TV"`` or ``"R"``.
        year: 4-digit year.
        serial: the document's serial number within that year.
        issuer: NJT issuer code, case-sensitive (required except for ``"TV"``).
        date: optional ``YYYY-MM-DD`` (version in force that day) or ``"kozlony"``.
        start: character offset to read from (0 = beginning).
        max_chars: page size, 1000-60000 (default 20000).
        search: optional phrase to locate, e.g. ``"garazdasag"``.
    """
    audit = _audit()
    dt = _check_code("doc_type", doc_type)
    y = _check_year(year)
    s = _check_serial(serial)
    d = _check_date(date)
    st, mx = _check_paging(start, max_chars)
    if dt == "TV":
        iss = None
        eli_path = f"/eli/TV/{y}/{s}"
    else:
        if not issuer:
            raise ToolError("invalid_arg", "issuer is required for doc_type other than 'TV'.")
        iss = _check_code("issuer", issuer)
        eli_path = f"/eli/{dt}/{y}/{iss}/{s}"
    if d:
        eli_path += f"/{d}"
    input_hash = hash_input({"tool": "hu_read_text", "doc_type": dt, "year": y, "issuer": iss,
                             "serial": s, "date": d, "start": st, "max_chars": mx,
                             "search": search})

    with timer() as t:
        try:
            async with NjtClient(base_url=_base_url()) as client:
                source_url, html = await client.resolve_eli(eli_path)
                html = await client.load_complete_text(source_url, html)
        except Exception as exc:
            audit.log(tool="hu_read_text", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    result = _text_page(
        doc_type=dt, year=y, serial=s, issuer=iss, issuer_name=None, date=d, eli_path=eli_path,
        source_url=source_url, html=html, start=st, max_chars=mx, search=search,
    )
    audit.log(tool="hu_read_text", input_hash=input_hash, output_count_or_size=len(result.text),
              duration_ms=t.duration_ms, status="ok")
    return result


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
