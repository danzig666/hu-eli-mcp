"""Offline tests for municipal issuer lookup and the paged plain-text view."""

from __future__ import annotations

import pytest

from hu_eli_mcp.local import (
    AmbiguousMunicipalityError,
    resolve_municipality,
    search_municipalities,
)
from hu_eli_mcp.server import ToolError, _check_date, _check_local_type, _check_paging
from hu_eli_mcp.textview import extract, html_to_text, page, search_text

# Rows as NJT's /eli/kshkodok lists them (names deliberately non-uniform).
ROWS = [
    ("735584", "Debrecen Megyei Jogú Város Önkormányzata"),
    ("728373", "Ebes Község Önkormányzata"),
    ("726753", "Fábiánsebestyén Községi Önkormányzat"),
    ("728317", "Hajdú-Bihar Megyei Önkormányzat"),
    ("735638", "Budapest Főváros Önkormányzata"),
    ("735748", "Budapest Főváros XI. Kerület Újbuda Önkormányzata"),
    ("735650", "Budapest Főváros II. Kerületi Önkormányzat"),
    ("728944", "Heves Megyei Önkormányzat"),
    ("729293", "Heves Város Önkormányzata"),
    ("729480", "Hevesaranyos Község Önkormányzata"),
]


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ("Debrecen", "735584"),
        ("debrecen", "735584"),
        ("Ebes", "728373"),  # not Fabiansebestyen, which merely contains "ebes"
        ("hajdu-bihar", "728317"),
        ("Budapest", "735638"),  # the capital itself, not a district
        ("Budapest XI", "735748"),
        ("735584", "735584"),
    ],
)
def test_resolve_municipality(query, code):
    assert resolve_municipality(ROWS, query).code == code


def test_ambiguous_name_is_rejected_with_candidates():
    with pytest.raises(AmbiguousMunicipalityError) as info:
        resolve_municipality(ROWS, "Heves")
    assert {m.code for m in info.value.candidates} == {"728944", "729293"}


def test_unknown_name_raises_lookup_error():
    with pytest.raises(LookupError):
        resolve_municipality(ROWS, "Nincsilyenfalva")


def test_search_ranks_settlement_match_first():
    found = search_municipalities(ROWS, "heves")
    assert [m.code for m in found][:2] == ["728944", "729293"]
    assert found[-1].code == "729480"


PAGE = """
<html><body><nav>Ugrás a tartalomra</nav>
<script>var x = "<div>not text</div>";</script>
<span class="jhId" id="NR"></span>
<h1 id="sc2020-47-SP-5Y1578-3" class="pslice jogszabalyMainTitle">Ebes Község 9/2017 rendelete</h1>
<h2 id="sc2020-47-SP-5Y1578-4" class="jogszabalySubtitle">a helyi építési szabályzatról</h2>
<div id="sc2020-47-SP-5Y1578-19" class="bekezdesNyito"><p><span class="szakasz-jel">1. §</span>
(1) Az övezet<sup class="fnSup" data-note-id="fnr_1">1</sup>jele Lke-1.</p></div>
<div class="footnote" id="fnr_1"><sup>1</sup><p>Módosította a 3/2020. rendelet.</p></div>
<div id="sc2020-47-SP-5Y1578-20" class="TABLE"><table>
<tr><td><p>1</p></td><td><p>Lke-1</p>
</td><td>720</td></tr>
<tr><td>2</td><td>Gksz</td><td>2000</td></tr></table></div>
<div id="sc2020-47-SP-5Y1578-30" class="mellekletPont"><b>1.1. melléklet</b></div>
<div id="sc2020-47-SP-5Y1578-31" class="szelet">
<a href="/document/91/terv.pdf">(A melléklet szövegét
a(z) terv.pdf elnevezésű fájl tartalmazza.)</a></div>
<footer>Kapcsolat</footer>
</body></html>
"""


def test_html_to_text_keeps_legal_text_only():
    text, attachments = extract(PAGE)
    assert text.startswith("Ebes Község 9/2017 rendelete")
    assert "Ugrás a tartalomra" not in text and "not text" not in text
    assert "Kapcsolat" not in text
    assert "Módosította" not in text  # footnote body dropped
    assert "övezet jele" in text  # footnote marker dropped without gluing words
    assert "| 1 | Lke-1 | 720" in text  # one table row per line
    assert "| 2 | Gksz | 2000" in text
    assert "[PDF: https://njt.jog.gov.hu/document/91/terv.pdf]" in text
    assert attachments == [
        {
            "title": "1.1. melléklet: (A melléklet szövegét a(z) terv.pdf elnevezésű fájl "
            "tartalmazza.)",
            "url": "https://njt.jog.gov.hu/document/91/terv.pdf",
        }
    ]


def test_search_is_case_and_accent_insensitive_with_valid_offsets():
    text = html_to_text(PAGE)
    hits = search_text(text, "ovezet JELE")
    assert len(hits) == 1
    assert text[hits[0]["start"] :].lower().startswith("övezet jele")


def test_paging_covers_the_text_exactly_once():
    text = "\n".join(f"{i}. § sor" for i in range(2000))
    pieces, start = [], 0
    while True:
        chunk, end, next_start = page(text, start, 1000)
        pieces.append(chunk)
        assert len(chunk) <= 1000
        if next_start is None:
            break
        assert next_start == end
        start = next_start
    assert "".join(pieces) == text


def test_argument_checks():
    assert _check_date("2023-01-01") == "2023-01-01"
    assert _check_date("kozlony") == "kozlony"
    assert _check_date(None) is None
    assert _check_local_type("or") == "OR"
    assert _check_paging(0, 20000) == (0, 20000)
    for bad in (lambda: _check_date("2023.01.01"), lambda: _check_local_type("R"),
                lambda: _check_paging(-1, 20000), lambda: _check_paging(0, 10)):
        with pytest.raises(ToolError, match="invalid_arg"):
            bad()
