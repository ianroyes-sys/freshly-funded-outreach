#!/usr/bin/env python3
"""Rebuild dashboard/index.html from drafts/, sent/, and ledger/. Stdlib only, deterministic.

Usage: python3 scripts/build_dashboard.py   (from the project root)
Run after every pass — costs nothing and keeps the dashboard current.
"""
import html
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
SENT = ROOT / "sent"
COMPANIES = ROOT / "ledger" / "companies.jsonl"
SEEN = ROOT / "ledger" / "seen-issues.jsonl"
APPROVE = ROOT / "APPROVE"
OUT = ROOT / "dashboard" / "index.html"

FIELD_RE = re.compile(r"^\*\*(.+?):\*\*\s*(.+)$")
TITLE_RE = re.compile(r"^#\s+(.+?)\s+—\s+(.+)$")


def esc(s):
    return html.escape(str(s), quote=True)


def parse_email_md(path):
    doc = {"file": path.name, "company": path.stem, "fields": {}}
    for line in path.read_text().splitlines():
        m = TITLE_RE.match(line.strip())
        if m:
            doc["company"] = m.group(1).strip()
            continue
        m = FIELD_RE.match(line.strip())
        if m:
            doc["fields"][m.group(1).strip().lower()] = m.group(2).strip()
    return doc


def get(doc, key, default="—"):
    return doc["fields"].get(key, default)


def fit_of(doc):
    m = re.search(r"(\d+)\s*/\s*10", get(doc, "fit score", ""))
    return int(m.group(1)) if m else 0


def variant_of(doc):
    v = get(doc, "variant", "")
    return "B" if v.upper().startswith("B") else "A"


def send_after_date(doc):
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", get(doc, "send after", ""))
    if m:
        try:
            return datetime(*map(int, m.groups()))
        except ValueError:
            pass
    return None


def load_companies():
    if not COMPANIES.exists():
        return []
    rows = []
    for line in COMPANIES.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_seen():
    if not SEEN.exists():
        return []
    rows = []
    for line in SEEN.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def md_inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


def draft_card(doc):
    fit = fit_of(doc)
    variant = variant_of(doc)
    send_after = get(doc, "send after")
    stars = "★" * min(fit, 10) + "☆" * max(0, 10 - fit)
    sd = send_after_date(doc)
    ready = sd is not None and sd <= datetime.now()
    return f"""
    <article class="card{' card-ready' if ready else ''}">
      <div class="cardtop">
        <span class="chip chip-variant{esc(variant)}">Variant {esc(variant)}</span>
        <span class="pill {'pill-good' if ready else 'pill-warn'}">
          {'Ready to send' if ready else 'Waiting'}
        </span>
      </div>
      <h3>{esc(doc['company'])}</h3>
      <dl>
        <div><dt>Fit</dt><dd><span class="stars">{stars}</span> {fit}/10</dd></div>
        <div><dt>Send after</dt><dd>{md_inline(send_after)}</dd></div>
      </dl>
    </article>"""


def queued_card(row):
    return f"""
    <article class="card card-queued">
      <div class="cardtop">
        <span class="chip chip-variantB">Variant B</span>
        <span class="pill pill-muted">Artifact pending</span>
      </div>
      <h3>{esc(row.get('company', '?'))}</h3>
      <dl>
        <div><dt>Fit</dt><dd>{esc(row.get('score', '?'))}/10</dd></div>
        <div><dt>Seen</dt><dd>{esc(row.get('seen', '—'))}</dd></div>
      </dl>
      <p class="reason">{md_inline(row.get('reason', ''))}</p>
    </article>"""


def main():
    draft_docs = [parse_email_md(p) for p in sorted(DRAFTS.glob("*.md"))] if DRAFTS.exists() else []
    sent_docs = [parse_email_md(p) for p in sorted(SENT.glob("*.md"))] if SENT.exists() else []
    companies = load_companies()
    seen = load_seen()

    drafted_names = {d["company"].lower() for d in draft_docs}
    queued = [c for c in companies
              if c.get("status") == "queued-variant-b" and c.get("company", "").lower() not in drafted_names]

    ready_now = [d for d in draft_docs if (send_after_date(d) or datetime.max) <= datetime.now()]
    total_kept = sum(row.get("kept", 0) for row in seen)

    approve_pending = APPROVE.exists()
    if draft_docs and ready_now and approve_pending:
        approve_html = (
            '<div class="approve approve-go"><div><strong>&check; APPROVE file present.</strong> '
            f'{len(ready_now)} draft(s) whose send date has passed will go out next run '
            '(max 5/day, 15/week).</div></div>')
    elif ready_now:
        names = ", ".join(esc(d["company"]) for d in ready_now)
        approve_html = f"""<div class="approve"><div>
      <strong>{len(ready_now)} draft(s) past their send date, waiting on you</strong>
      <p class="approvenames">{names}</p>
      <p class="approvehow">Read them in <code>drafts/</code>, then approve the batch:
      <code>touch ~/Developer/vc-outreach/APPROVE</code> in Terminal.
      Nothing sends until you do.</p>
    </div></div>"""
    else:
        approve_html = ""

    tiles = [
        ("Drafts awaiting you", len(draft_docs), "in drafts/"),
        ("Past send date", len(ready_now), "ready once approved"),
        ("Queued (Variant B)", len(queued), "teardown artifact pending"),
        ("Sent", len(sent_docs), "all time"),
        ("Companies tracked", len(companies), "never emailed twice"),
        ("Issues parsed", len(seen), f"{total_kept} funding entries kept"),
    ]
    tiles_html = "".join(
        f'<div class="tile"><span class="tilenum">{n}</span>'
        f'<span class="tilelabel">{esc(t)}</span>'
        f'<span class="tilesub">{esc(s)}</span></div>'
        for t, n, s in tiles)

    draft_cards_html = "".join(draft_card(d) for d in draft_docs) or \
        '<p class="empty">No drafts waiting — nothing passed the filter last pass.</p>'
    queued_cards_html = "".join(queued_card(c) for c in queued)

    sent_rows_html = "".join(
        f'<tr><td>{esc(d["company"])}</td><td>{md_inline(get(d, "status"))}</td>'
        f'<td>{md_inline(get(d, "fit score"))}</td></tr>'
        for d in sent_docs) or '<tr><td colspan="3">Nothing sent yet.</td></tr>'
    sent_table_html = f"""<table class="senttable">
        <thead><tr><th>Company</th><th>Status</th><th>Fit</th></tr></thead>
        <tbody>{sent_rows_html}</tbody>
      </table>"""

    now = datetime.now().strftime("%b %d, %Y · %I:%M %p")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Freshly-Funded — VC Outreach</title>
<style>
:root {{
  --bg:#0c0e12; --surface:#14171d; --surface2:#1a1e26; --border:#262b35;
  --ink:#eef1f6; --ink2:#9aa3b2; --ink3:#6b7484;
  --accent:#4ade80; --accent2:#a8792b;
  --good:#4ade80; --warn:#fbbf24; --bad:#f87171;
}}
@media (prefers-color-scheme: light) {{
  :root {{ --bg:#f6f7f9; --surface:#ffffff; --surface2:#f0f2f5; --border:#e3e6ec;
    --ink:#171b22; --ink2:#525a68; --ink3:#8a92a1;
    --accent:#15803d; --accent2:#b45309;
    --good:#15803d; --warn:#b45309; --bad:#b91c1c; }}
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--ink); min-height:100vh;
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;
  -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:40px 24px 80px; }}
header {{ display:flex; flex-wrap:wrap; gap:16px; align-items:flex-end;
  justify-content:space-between; margin-bottom:8px; }}
h1 {{ font-size:26px; letter-spacing:-.02em; font-weight:750; }}
h1 .grad {{ background:linear-gradient(90deg,var(--accent),var(--accent2));
  -webkit-background-clip:text; background-clip:text; color:transparent; }}
.meta {{ color:var(--ink3); font-size:13px; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:12px; margin:28px 0 36px; }}
.tile {{ background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:18px 20px; display:flex; flex-direction:column; gap:2px; }}
.tilenum {{ font-size:30px; font-weight:750; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums; }}
.tilelabel {{ font-size:13px; font-weight:600; color:var(--ink2); }}
.tilesub {{ font-size:12px; color:var(--ink3); }}
h2 {{ font-size:15px; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
  color:var(--ink2); margin:36px 0 14px; }}
.approve {{ background:color-mix(in srgb,var(--accent) 12%,var(--surface));
  border:1px solid color-mix(in srgb,var(--accent) 45%,var(--border));
  border-radius:16px; padding:18px 22px; margin:24px 0 4px; }}
.approve-go {{ background:color-mix(in srgb,var(--good) 14%,var(--surface));
  border-color:color-mix(in srgb,var(--good) 50%,var(--border)); }}
.approve strong {{ font-size:16px; }}
.approvenames {{ color:var(--ink2); font-size:13.5px; margin-top:4px; }}
.approvehow {{ color:var(--ink3); font-size:13px; margin-top:8px; }}
.approve code {{ background:var(--surface2); border:1px solid var(--border);
  border-radius:6px; padding:2px 7px; font-size:12.5px; color:var(--ink); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:14px; }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:18px;
  padding:20px; display:flex; flex-direction:column; gap:10px; }}
.card-ready {{ border-left:3px solid var(--good); }}
.card-queued {{ border-left:3px solid var(--ink3); opacity:.85; }}
.cardtop {{ display:flex; justify-content:space-between; gap:8px; align-items:center; }}
.chip {{ font-size:11px; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
  padding:3px 10px; border-radius:999px; border:1px solid; }}
.chip-variantA {{ color:var(--accent); border-color:var(--accent); }}
.chip-variantB {{ color:var(--accent2); border-color:var(--accent2); }}
.pill {{ display:inline-flex; align-items:center; gap:5px; font-size:12px; font-weight:600;
  padding:3px 10px; border-radius:999px; background:var(--surface2); color:var(--ink2); }}
.pill-good {{ color:var(--good); }} .pill-warn {{ color:var(--warn); }} .pill-muted {{ color:var(--ink3); }}
.card h3 {{ font-size:16.5px; font-weight:700; letter-spacing:-.01em; }}
dl {{ display:flex; flex-direction:column; gap:6px; font-size:13px; }}
dl div {{ display:flex; gap:8px; }}
dt {{ color:var(--ink3); min-width:70px; flex-shrink:0; }}
dd {{ color:var(--ink2); }}
.stars {{ color:var(--warn); letter-spacing:1px; }}
.reason {{ font-size:12.5px; color:var(--ink3); }}
.senttable {{ width:100%; border-collapse:collapse; background:var(--surface);
  border:1px solid var(--border); border-radius:16px; overflow:hidden; }}
.senttable th, .senttable td {{ padding:12px 20px; text-align:left; font-size:13.5px; }}
.senttable thead th {{ color:var(--ink3); font-weight:600; font-size:12px;
  text-transform:uppercase; letter-spacing:.04em; border-bottom:1px solid var(--border); }}
.senttable tbody tr:not(:last-child) td {{ border-bottom:1px solid var(--border); }}
.empty {{ color:var(--ink3); }}
strong {{ color:var(--ink); font-weight:650; }}
footer {{ margin-top:48px; color:var(--ink3); font-size:12px; text-align:center; }}
</style></head><body>
<div class="wrap">
  <header>
    <div>
      <h1>Freshly-<span class="grad">Funded</span></h1>
      <p class="meta">Freshly-Funded outreach loop · updated {now}</p>
    </div>
  </header>

  <div class="tiles">{tiles_html}</div>

  {approve_html}

  <h2>Drafts — awaiting approval</h2>
  <div class="grid">{draft_cards_html}</div>

  <h2>Queued — Variant B teardown pending</h2>
  <div class="grid">{queued_cards_html or '<p class="empty">Nothing queued.</p>'}</div>

  <h2>Sent</h2>
  {sent_table_html}

  <footer>Generated by scripts/build_dashboard.py — refresh after every loop pass</footer>
</div>
</body></html>"""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page)
    print(f"Dashboard written: {OUT} ({len(draft_docs)} drafted, {len(queued)} queued, {len(sent_docs)} sent)")


if __name__ == "__main__":
    main()
