"""Municipal (local government) decrees: issuer lookup by settlement name.

NJT's ELI scheme addresses municipal decrees as ``/eli/{ortip}/{ev}/{orkib}[/{sr}[/{date}]]``
(documented at ``/eli/urisemak``), where ``ortip`` is ``OR`` (onkormanyzati rendelet) or ``RI``
(rendelet indokolas) and ``orkib`` is a numeric code from the table at ``/eli/kshkodok``
("ELI parameter" -> "Telepules neve"), e.g. ``735584`` = Debrecen Megyei Jogu Varos
Onkormanyzata. The table also lists the county governments and the Budapest districts.

Names in that table are not uniform ("Fejer Megyei Onkormanyzat" vs "Bacs-Kiskun Megye
Onkormanyzata", "Alacska Kozseg Onkormanyzat" vs "... Onkormanyzata"), so matching is done on
an accent- and case-insensitive normalised form, ranking a settlement-name match above a
plain substring match. A query that matches more than one issuer is never resolved by
guessing.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

LOCAL_DOC_TYPES = {"OR": "onkormanyzati rendelet", "RI": "rendelet indokolas"}
KSH_CODE_RE = re.compile(r"^\d{5,7}$")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}|kozlony)$")

# Words that follow the settlement name in the issuer names of /eli/kshkodok.
_TYPE_WORDS = {
    "kozseg", "kozsegi", "nagykozseg", "nagykozsegi", "varos", "varosi", "megyei", "megye",
    "telepules", "telepulesi", "onkormanyzat", "onkormanyzata", "fovaros", "kerulet",
    "keruleti", "jogu",
}


def normalise(text: str) -> str:
    """Lower-case, accent-free, single-spaced form used for matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


@dataclass(frozen=True)
class Municipality:
    code: str
    name: str


def _rank(query: str, name: str) -> int | None:
    """0 = settlement name exact, 1 = prefix, 2 = substring, 3 = all query words present."""
    norm = normalise(name)
    if norm == query:
        return 0
    if norm.startswith(query + " "):
        # "Debrecen Megyei Jogu Varos Onkormanyzata" is Debrecen itself; "Budapest Fovaros
        # XI. Kerulet Ujbuda Onkormanyzata" only starts with "Budapest".
        rest = norm[len(query) + 1 :].split()
        return 0 if all(word in _TYPE_WORDS for word in rest) else 1
    if norm.startswith(query):
        return 1
    if query in norm:
        return 2
    # Every query word appears as a word of the name, e.g. "budapest xi" matches
    # "Budapest Fovaros XI. Kerulet Ujbuda Onkormanyzata".
    name_words = set(re.findall(r"[\w-]+", norm))
    query_words = re.findall(r"[\w-]+", query)
    if query_words and all(word in name_words for word in query_words):
        return 3
    return None


def search_municipalities(
    rows: list[tuple[str, str]], query: str, limit: int = 20
) -> list[Municipality]:
    """Find issuers in the /eli/kshkodok table by code or (part of) name, best match first."""
    cleaned = query.strip()
    if KSH_CODE_RE.match(cleaned):
        return [Municipality(code, name) for code, name in rows if code == cleaned][:limit]

    q = normalise(cleaned)
    if not q:
        return []
    ranked: list[tuple[int, str, Municipality]] = []
    for code, name in rows:
        rank = _rank(q, name)
        if rank is not None:
            ranked.append((rank, normalise(name), Municipality(code, name)))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


class AmbiguousMunicipalityError(ValueError):
    def __init__(self, query: str, candidates: list[Municipality]):
        self.candidates = candidates
        listing = "; ".join(f"{m.code} = {m.name}" for m in candidates[:10])
        super().__init__(
            f"municipality={query!r} matches more than one issuer: {listing}. "
            "Pass the numeric code of the intended one."
        )


def resolve_municipality(rows: list[tuple[str, str]], query: str) -> Municipality:
    """Resolve a code or name to exactly one issuer, or raise.

    A name resolves only if exactly one issuer has it as its settlement name (rank 0), or
    the query matches exactly one issuer at all. Anything else is ambiguous.
    """
    matches = search_municipalities(rows, query, limit=50)
    if not matches:
        raise LookupError(
            f"No municipality matching {query!r} in NJT's /eli/kshkodok table. "
            "Use hu_find_municipality with a shorter part of the name."
        )
    if len(matches) == 1:
        return matches[0]
    q = normalise(query)
    exact = [m for m in matches if _rank(q, m.name) == 0]
    if len(exact) == 1:
        return exact[0]
    raise AmbiguousMunicipalityError(query, exact or matches)
