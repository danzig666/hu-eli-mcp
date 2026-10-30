"""Pydantic v2 models for Hungarian legislation (Nemzeti Jogszabalytar / njt.jog.gov.hu)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DATASET_NOTE = (
    "Nemzeti Jogszabalytar (NJT) is Hungary's official, free-to-use national legislation "
    "database, maintained by MKIFK (Magyar Kozlonykiado es Igazsagugyi Forditokozpont Zrt.) "
    "at njt.jog.gov.hu. Hungary publishes a genuine, documented national ELI (European "
    "Legislation Identifier) URI scheme since 2023 (see /eli/urisemak). Each ELI URI resolves "
    "(HTTP 302) to a partially server-rendered HTML page. Large acts may include deferred "
    "statutory or annex blocks; hu_get_text reconstructs them via NJT internal AJAX requests. "
    "There is no documented public REST/JSON search API; the search/browse UI is an AngularJS SPA "
    "that requires a session and JavaScript; documents must be addressed by a known ELI "
    "(type + year + serial, and an issuer code for non-Act types)."
)


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Legislation(_Tolerant):
    """A Hungarian piece of legislation resolved via its ELI URI."""

    doc_type: str | None = None
    year: str | None = None
    serial: str | None = None
    issuer: str | None = None

    title: str | None = None
    """The citation-style number, e.g. '2013. evi V. torveny' (parsed h1 mainTitle)."""

    subtitle: str | None = None
    """The subject of the act, e.g. 'a Polgari Torvenykonyvrol' (parsed h2 subtitle)."""

    in_force_date: str | None = None
    """The 'hatalyos' as-of date shown on the page (YYYY.MM.DD., Hungarian format), if present."""

    # Citation contract (Art. IV CONSTITUTION).
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None

    dataset_note: str = DATASET_NOTE


class LegislationText(_Tolerant):
    """Result of ``hu_get_text`` - the full document HTML/text of one act."""

    doc_type: str
    year: str
    serial: str
    issuer: str | None = None

    title: str | None = None
    subtitle: str | None = None
    in_force_date: str | None = None

    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None

    format: str = "njt-html-fragment"
    content: str | None = None
    byte_size: int | None = None
    dataset_note: str = DATASET_NOTE


class DocTypeInfo(_Tolerant):
    """One row of the NJT document-type code list (/eli/tipuskodok)."""

    code: str
    name: str | None = None


class DocTypeList(_Tolerant):
    """Result of ``hu_list_doc_types``."""

    items: list[DocTypeInfo] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE


class IssuerInfo(_Tolerant):
    """One row of the NJT issuer code list (/eli/kibocsatokodok)."""

    code: str
    name: str | None = None


class IssuerList(_Tolerant):
    """Result of ``hu_list_issuers``."""

    items: list[IssuerInfo] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE


class MunicipalityInfo(_Tolerant):
    """One issuer of municipal decrees from /eli/kshkodok (settlement, county or district)."""

    code: str
    """The numeric ELI issuer parameter, e.g. '735584' (Debrecen)."""

    name: str
    """The issuing local government as NJT names it."""


class MunicipalityList(_Tolerant):
    """Result of ``hu_find_municipality`` - best match first."""

    query: str
    items: list[MunicipalityInfo] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE


class TextMatch(_Tolerant):
    """One hit of a search inside a document's plain text."""

    start: int
    """Character offset in the plain text; pass it as ``start`` to read from there."""

    snippet: str


class AttachmentInfo(_Tolerant):
    """An annex NJT publishes only as an attached file (e.g. a plan sheet)."""

    title: str
    url: str


class TextPage(_Tolerant):
    """One page of a document's plain legal text (footnotes and page chrome removed)."""

    doc_type: str
    year: str
    serial: str
    issuer: str | None = None
    issuer_name: str | None = None
    date: str | None = None
    """The requested point in time (YYYY-MM-DD or 'kozlony'); None = in force now."""

    title: str | None = None
    subtitle: str | None = None
    in_force_date: str | None = None
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None

    start: int
    end: int
    total_chars: int
    next_start: int | None = None
    """Offset of the next page, or None when this page reaches the end of the document."""

    complete: bool
    """True only when this single page contains the whole document."""

    text: str
    matches: list[TextMatch] = Field(default_factory=list)
    attachments: list[AttachmentInfo] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE
