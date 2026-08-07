"""Vocabulary scraper — extract candidate NSL entries into a STAGING csv.

It never writes ``ml/data/vocabulary.csv`` directly: scraped entries carry placeholder
phonology (handshape / location / movement / orientation) and must be completed and approved
by a human + the ``nsl-data-reviewer`` before they enter training. IDs are language-neutral
(``NSL_dddd``), never English words.

ETHICS / ToS: only point this at a source you are permitted to scrape. It sends a descriptive
User-Agent and can honour robots.txt with ``--check-robots``. HTML parsing uses the standard
library (no BeautifulSoup needed), so the parsing is unit-testable offline.

    python tools/scrape_vocabulary/scrape.py --url https://example.org/nsl-dictionary \\
        --out tools/scrape_vocabulary/staging_vocab.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_VOCAB = _ROOT / "ml" / "data" / "vocabulary.csv"
_USER_AGENT = "SignBridgeVocabBot/0.1 (+research; contact project maintainer)"

# vocabulary.csv column order (phonology left blank for review).
_COLUMNS = [
    "sign_id", "en", "ne", "ne_roman", "gloss_code", "handshape", "location", "movement",
    "orientation", "two_handed", "symmetric", "eyebrows", "head", "category", "difficulty",
    "phase", "prerequisites",
]


class _TableExtractor(HTMLParser):
    """Collect rows of cell texts from every <table> in the document."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())  # type: ignore[union-attr]
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(c for c in self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_html(html: str, en_col: int = 0, ne_col: int = 1) -> list[dict[str, str]]:
    """Extract {en, ne} entries from table rows. Skips header/blank rows."""
    extractor = _TableExtractor()
    extractor.feed(html)
    out: list[dict[str, str]] = []
    for cells in extractor.rows:
        if len(cells) <= max(en_col, ne_col):
            continue
        en = cells[en_col].strip()
        ne = cells[ne_col].strip()
        if not en or en.lower() in ("english", "word", "gloss"):  # header row
            continue
        out.append({"en": en, "ne": ne})
    return out


def _existing(vocab_path: Path = _VOCAB) -> tuple[set[str], int]:
    """Return (lowercased english labels already present, highest NSL_dddd number)."""
    labels: set[str] = set()
    max_id = 0
    if vocab_path.exists():
        for row in csv.DictReader(vocab_path.open(encoding="utf-8")):
            labels.add((row.get("en") or "").strip().lower())
            m = re.match(r"NSL_(\d+)", row.get("sign_id") or "")
            if m:
                max_id = max(max_id, int(m.group(1)))
    return labels, max_id


def to_rows(entries: list[dict[str, str]], vocab_path: Path = _VOCAB) -> list[dict[str, str]]:
    """Convert scraped entries to staging rows: dedupe vs existing, assign IDs + gloss codes,
    leave phonology blank for human/reviewer completion."""
    existing, max_id = _existing(vocab_path)
    seen = set(existing)
    rows: list[dict[str, str]] = []
    for e in entries:
        en = e["en"].strip()
        key = en.lower()
        if not en or key in seen:
            continue
        seen.add(key)
        max_id += 1
        gloss = re.sub(r"[^A-Z0-9]+", "-", en.upper()).strip("-")
        rows.append({
            "sign_id": f"NSL_{max_id:04d}",
            "en": en,
            "ne": e.get("ne", "").strip(),
            "ne_roman": "",
            "gloss_code": gloss,
            "handshape": "", "location": "", "movement": "", "orientation": "",
            "two_handed": "false", "symmetric": "false",
            "eyebrows": "neutral", "head": "neutral",
            "category": "scraped", "difficulty": "1", "phase": "", "prerequisites": "",
        })
    return rows


def write_staging(rows: list[dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def fetch(url: str, timeout: float = 20.0, check_robots: bool = False) -> str:
    if check_robots and not _robots_allows(url):
        raise SystemExit(f"robots.txt disallows scraping {url}")
    try:
        import requests
    except ImportError as exc:  # requests is in the optional `tools` extra
        raise SystemExit("install the tools extra: pip install -e 'ml[tools]'") from exc
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _robots_allows(url: str) -> bool:
    from urllib.parse import urlsplit
    from urllib.robotparser import RobotFileParser

    parts = urlsplit(url)
    rp = RobotFileParser()
    rp.set_url(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True  # no robots.txt reachable -> not disallowed
    return rp.can_fetch(_USER_AGENT, url)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True, help="source dictionary page URL")
    p.add_argument("--out", default=str(Path(__file__).with_name("staging_vocab.csv")))
    p.add_argument("--en-col", type=int, default=0)
    p.add_argument("--ne-col", type=int, default=1)
    p.add_argument("--check-robots", action="store_true")
    args = p.parse_args(argv)

    html = fetch(args.url, check_robots=args.check_robots)
    entries = parse_html(html, args.en_col, args.ne_col)
    rows = to_rows(entries)
    write_staging(rows, Path(args.out))
    print(f"scraped {len(entries)} entries -> {len(rows)} new staged rows in {args.out}")
    print("Next: a human + nsl-data-reviewer complete the phonology before training.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
