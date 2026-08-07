"""Vocabulary scraper: HTML parsing + staging conversion are tested offline (no network).
The scraper lives under tools/, so it's loaded by path rather than imported as a package."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

_SCRAPE = Path(__file__).resolve().parents[2] / "tools" / "scrape_vocabulary" / "scrape.py"


def _load():
    spec = importlib.util.spec_from_file_location("scrape_vocab", _SCRAPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_HTML = """
<html><body><table>
  <tr><th>English</th><th>Nepali</th></tr>
  <tr><td>Water</td><td>पानी</td></tr>
  <tr><td>Friend</td><td>साथी</td></tr>
  <tr><td></td><td>skip me</td></tr>
</table></body></html>
"""


def test_parse_html_extracts_entries_and_skips_header_and_blank():
    m = _load()
    entries = m.parse_html(_HTML)
    ens = [e["en"] for e in entries]
    assert ens == ["Water", "Friend"]  # header + blank-english rows dropped
    assert entries[0]["ne"] == "पानी"


def test_to_rows_assigns_ids_gloss_and_dedupes(tmp_path):
    m = _load()
    # A tiny existing vocab so we can assert IDs continue and dedupe works.
    vocab = tmp_path / "vocabulary.csv"
    with vocab.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sign_id", "en"])
        w.writeheader()
        w.writerow({"sign_id": "NSL_0007", "en": "Water"})  # already present

    rows = m.to_rows(m.parse_html(_HTML), vocab_path=vocab)
    assert [r["en"] for r in rows] == ["Friend"]  # "Water" deduped out
    assert rows[0]["sign_id"] == "NSL_0008"  # continues after the max existing id
    assert rows[0]["gloss_code"] == "FRIEND"  # language-neutral, uppercased
    assert rows[0]["handshape"] == ""  # phonology left blank for review
    assert rows[0]["category"] == "scraped"
