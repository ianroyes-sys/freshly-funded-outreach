#!/usr/bin/env python3
"""
StrictlyVC issue -> structured funding entries (JSONL on stdout).

IMPORTANT: this parser was written against the newsletter's known section headings, not
verified on a large set of real issues. So it is built to be *checked*,
not trusted: every entry carries `raw_text` and a `confidence`, and the loop agent
re-reads the raw text and corrects the extraction before anything is drafted.

Treat low confidence as "read it yourself", not "drop it".

Usage:
    python3 scripts/parse_issue.py issue.txt
    python3 scripts/parse_issue.py --self-test
    gws gmail +read --params '{"id":"<msgId>"}' | python3 scripts/parse_issue.py -
"""

from __future__ import annotations

import json
import re
import sys

# Section headings StrictlyVC uses for rounds. Everything else is ignored.
# Markdown emails render these as "## Heading" — allow an optional "#" prefix.
FUNDING_HEADS = re.compile(
    r"^\s*#{0,6}\s*(massive fundings?|big-?er fundings?|"
    r"big-but-not-crazy-big fundings?|smaller fundings?|new fundings?|fundings?)"
    r"\s*:?\s*$",
    re.I,
)
# Headings that mean we've left the funding sections.
# "Prefer-Not-to-Say Fundings" lists undisclosed-amount rounds — not usable, so it's
# a stop head rather than a funding head (no amount means no sweet-spot filter to apply).
STOP_HEADS = re.compile(
    r"^\s*#{0,6}\s*(new funds?|exits?|people|data|essential reads?|detours?|"
    r"retail therapy|top news|sponsored|job listings?|going public|post-?its?|"
    r"brain rot|prefer-not-to-say fundings?)\s*:?\s*$",
    re.I,
)

MONEY = re.compile(
    r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(billion|bn|b|million|mm|m|k)?\b",
    re.I,
)

STAGE = re.compile(
    r"\b(pre-?seed|seed|series\s+[a-k]|growth|bridge|angel|debt|"
    r"convertible|extension)\b",
    re.I,
)

# "Acme, a Boston-based maker of X, raised $6 million ..."
COMPANY = re.compile(r"^\s*\*{0,2}([A-Z][^,\n]{1,60}?)\*{0,2}\s*,\s")

LED_BY = re.compile(
    r"\bled by\s+([^.;]{3,120}?)(?:\.|;|,\s+(?:with|and)\b|$)", re.I
)
URL = re.compile(r"https?://[^\s<>\)\]]+")

MULT = {
    "b": 1_000_000_000, "bn": 1_000_000_000, "billion": 1_000_000_000,
    "m": 1_000_000, "mm": 1_000_000, "million": 1_000_000,
    "k": 1_000,
}


def to_usd(num: str, unit: str | None) -> int | None:
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    if unit:
        return int(v * MULT.get(unit.lower(), 1))
    # A bare "$6" in a funding line almost always means millions.
    return int(v * 1_000_000) if v < 1000 else int(v)


def strip_html(text: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&#39;", "'"),
                 ("&quot;", '"'), ("&mdash;", "—"), ("&rsquo;", "'")]:
        text = text.replace(a, b)
    return text


def funding_blocks(text: str) -> list[str]:
    """Return the raw paragraph blocks that sit under a funding heading."""
    lines = text.splitlines()
    inside = False
    buf: list[str] = []
    blocks: list[str] = []

    def flush():
        chunk = "\n".join(buf).strip()
        if chunk:
            blocks.append(chunk)
        buf.clear()

    for line in lines:
        if FUNDING_HEADS.match(line):
            flush()
            inside = True
            continue
        if STOP_HEADS.match(line):
            flush()
            inside = False
            continue
        if not inside:
            continue
        if not line.strip():
            flush()
        else:
            buf.append(line)
    flush()

    # An entry needs a dollar figure to be a funding entry at all.
    return [b for b in blocks if MONEY.search(b) and len(b) > 60]


def parse_entry(block: str) -> dict:
    flat = " ".join(block.split())

    m = MONEY.search(flat)
    amount = to_usd(m.group(1), m.group(2)) if m else None

    st = STAGE.search(flat)
    stage = re.sub(r"\s+", " ", st.group(1)).lower() if st else None

    c = COMPANY.match(block.strip())
    company = c.group(1).strip(" *") if c else None
    if not company:
        # Fall back to the first few words before a comma anywhere in the block.
        alt = re.match(r"\s*([A-Z][\w.\-& ]{1,40}?),", flat)
        company = alt.group(1).strip() if alt else None

    led = LED_BY.search(flat)
    investors = re.sub(r"\s+", " ", led.group(1)).strip(" ,.") if led else None

    urls = URL.findall(block)

    # Confidence is about whether a *human* needs to look, not correctness.
    confidence = sum([
        0.35 if company else 0,
        0.35 if amount else 0,
        0.20 if stage else 0,
        0.10 if investors else 0,
    ])

    return {
        "company": company,
        "amount_usd": amount,
        "stage": stage,
        "investors": investors,
        "urls": urls[:3],
        "confidence": round(confidence, 2),
        "raw_text": flat[:900],
    }


def in_sweet_spot(e: dict) -> bool:
    """$2M-$30M seed/A. See CLAUDE.md — megarounds are press releases, not hiring moments."""
    amt = e.get("amount_usd")
    if amt is None:
        return False
    return 2_000_000 <= amt <= 30_000_000


SAMPLE = """
Top News in the A.M.

Some macro story that is not a funding round at all.

New Fundings

Ledgerline, a Boston-based automation platform for accounting firms, raised $6 million in
seed funding led by Bessemer Venture Partners, with participation from Better Tomorrow
Ventures. TechCrunch has more here: https://techcrunch.com/basis

Northwind Robotics, a Pittsburgh-based warehouse automation company, raised $340 million
in Series D funding led by SoftBank Vision Fund.

Cadence Health, a New York-based benefits marketplace for SMBs, raised $18 million in
Series A funding led by Andreessen Horowitz, with participation from Lerer Hippeau.

New Funds

Some fund announcement that must not be parsed as a startup funding.
"""


def main() -> int:
    if "--self-test" in sys.argv:
        entries = [parse_entry(b) for b in funding_blocks(SAMPLE)]
        ok = True
        print(f"blocks found: {len(entries)} (expected 3)", file=sys.stderr)
        if len(entries) != 3:
            ok = False
        names = [e["company"] for e in entries]
        if names != ["Ledgerline", "Northwind Robotics", "Cadence Health"]:
            print(f"  FAIL company names: {names}", file=sys.stderr)
            ok = False
        amts = [e["amount_usd"] for e in entries]
        if amts != [6_000_000, 340_000_000, 18_000_000]:
            print(f"  FAIL amounts: {amts}", file=sys.stderr)
            ok = False
        keep = [e["company"] for e in entries if in_sweet_spot(e)]
        if keep != ["Ledgerline", "Cadence Health"]:
            print(f"  FAIL sweet-spot filter: {keep}", file=sys.stderr)
            ok = False
        for e in entries:
            print(json.dumps(e), file=sys.stderr)
        print("SELF-TEST PASS" if ok else "SELF-TEST FAIL", file=sys.stderr)
        return 0 if ok else 1

    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    raw = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8").read()
    if "<" in raw and ">" in raw:
        raw = strip_html(raw)

    blocks = funding_blocks(raw)
    if not blocks:
        print(
            "no funding sections matched — the newsletter format has probably changed. "
            "Read the issue by hand and update FUNDING_HEADS.",
            file=sys.stderr,
        )
        return 1

    for b in blocks:
        print(json.dumps(parse_entry(b)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
