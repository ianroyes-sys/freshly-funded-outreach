# Freshly-Funded: agent instructions

Watch the StrictlyVC newsletter. Find the startups that just raised. Find the right human.
Draft a real email. **Never send without the owner's approval.**

Everything about the sender comes from `profile/profile.md` (copy `profile/profile.example.md`
to start). **Never invent experience.** If a claim is not in the profile, it does not go in an email.

## One pass

1. Search the inbox for new StrictlyVC issues. Skip any Gmail message ID already in
   `ledger/seen-issues.jsonl`; append each new one after parsing.
2. Parse: `python3 scripts/parse_issue.py <file>` (or `-` for stdin). Every entry carries
   `raw_text` and `confidence`. Re-read the raw text and correct the extraction; never trust
   the regex alone.
3. For each funding entry, check `ledger/companies.jsonl`. A company is emailed once, ever.
4. Score 0–10 with the fit filter below. Under 6 is logged as `skipped` with a reason.
5. For 6+: research the product, find a published contact, and draft from
   `templates/variant-a-direct.md` (6–7) or `templates/variant-b-value-first.md` (8+, max 2–3 a week).
   One file per company in `drafts/`, with `**Fit score:**`, `**Send after:**`, `**Variant:**` fields.
6. Rebuild the dashboard: `python3 scripts/build_dashboard.py`.

## Non-negotiables

- **Gated outbound.** Nothing sends unless an `APPROVE` file exists at the repo root and the
  owner has read the draft. Record every send in `sent/` and `receipts/`.
- **5 sends/day, 15/week maximum.**
- **Max 3 pattern-guessed email addresses per day.** Bounces damage sending reputation for all
  of the owner's mail. No findable contact means skip the company.
- **Exactly one follow-up**, 6 days later, from `templates/follow-up.md`. Never a third.
- **No attachments.** One link.
- **Never open with "Congrats on the raise!"**

## Fit filter

| Take | Skip |
|---|---|
| Round $2M–$30M, seed / Series A | Series C+ (recruiters and ATS, cold email dies) |
| 3–30 people | Megarounds |
| Sectors listed in the profile | Sectors the profile can't speak to |
| Founder still reads their own inbox | `careers@` addresses with no human |

## Deliberate delay

Don't email the week of the announcement; the founder's inbox is flooded. Parse immediately,
set **Send after** to day 4–7.

## Gotchas

- Gmail message IDs are the dedupe key. Subject lines repeat; IDs don't.
- Never hand-edit the ledgers while a pass is running.
