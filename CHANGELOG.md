# Changelog

## 0.3.4 (unreleased)

- Fix `hu_get_text` silently returning truncated legislation when NJT defers
  sections and annexes behind AJAX block placeholders. The new implementation
  fetches missing blocks, reconstructs their original order, and fails closed
  rather than reporting incomplete text as a complete statute.
- Document reproducible cases: Criminal Code (26 deferred blocks), Civil Code
  (78 deferred blocks), and the Debrecen building regulation (2 deferred annex blocks).
- Add offline regression tests and live smoke tests for missing legal text.
- Clarify that NJT's `/ajax/njtGetBlock.json` is undocumented frontend plumbing,
  not a stable public REST API.

Note: the Claude plugin manifest and its `uv.lock` remain pinned to the
previously released 0.3.3 runtime until a 0.3.4 package is published and
the plugin lock can be regenerated against that published release.
