# Ledgers — the memory that stops repeats

- `seen-issues.jsonl` — one line per StrictlyVC Gmail **message ID** already parsed.
  Subject lines repeat; message IDs don't. This is the dedupe key.
  `{"msg_id":"...","date":"2026-07-28","entries":9,"kept":3}`

- `companies.jsonl` — one line per company **ever seen**. Checked before anything is
  drafted. A company is emailed exactly once, forever.
  `{"company":"Ledgerline","domain":"ledgerline.example","seen":"2026-07-28","score":9,"status":"drafted|sent|replied|skipped|closed","reason":"..."}`

Never hand-edit these while a loop pass is running.
