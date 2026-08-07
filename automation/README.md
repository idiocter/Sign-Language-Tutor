# Automation

Two ways to run the vocabulary harvest on a schedule — same underlying script.

## Idiomatic: a plain script (recommended)
`harvest_vocab.sh` scrapes → staging CSV. Drive it however you already schedule things:

```bash
# cron (weekly, Monday 03:00)
0 3 * * 1  NSL_SOURCE_URL=https://example.org/nsl /path/to/SignBridge/automation/harvest_vocab.sh
```

or a GitHub Action on a `schedule:` trigger calling the same script. No extra infra.

## Included for breadth: n8n
`n8n/signbridge-vocab-pipeline.json` is an importable workflow (Schedule → Execute Command →
count) that shells out to the same scraper. **This is the non-idiomatic path** — n8n is an
external service to host and maintain; for this repo a script + cron/CI is the native fit. It's
here to demonstrate the workflow-automation tool, not because the project needs it.

Import: n8n → *Workflows* → *Import from File*. Set env on the n8n host:
`SIGNBRIDGE_ROOT` (repo path) and `NSL_SOURCE_URL` (a permitted source). The workflow ships
`active: false` — review before enabling.
