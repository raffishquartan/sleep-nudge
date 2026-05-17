# generate-sleep-nudges - per-run algorithm

The model walks this algorithm step-by-step. Treat each numbered step as a checklist item.

## 0. Resolve inputs

Parse the range argument from the user's invocation:

- No arg -> `next30` (start = today + count of `GENERATED` future-dated entries; end = start + 29).
- `YYYY-MM` -> every date in that calendar month.
- `YYYY-MM-DD..YYYY-MM-DD` -> inclusive range.
- `YYYY-MM-DD` -> single date.
- `--force` flag -> overwrite existing `GENERATED` entries; otherwise skip them.

Resolve to an explicit list `dates_to_generate: list[str]` of ISO dates, sorted ascending.

## 1. Build used-history

Run `python -m scripts.build_used_history --entries-dir $ENTR --as-of $TODAY --window 90`.

It prints (and the model captures):

```yaml
used_stubs: ["...", "..."]
used_urls: ["https://...", "..."]
used_papers_by_url:
  "https://...": {first_used_in: "2026-04-12", title: "...", year: 2024}
```

This is the **dedup context**. `used_stubs` blocks stub re-use; `used_urls` is a soft signal the model uses to avoid re-citing the same paper.

## 2. Validate the bank

Run `python -m scripts.topic_picker --validate` (or read `data/day-categories.yaml` and `data/topic-bank.yaml` and check every category referenced in the day map is present in the bank with at least 1 stub remaining after the 90-day exclusion). Abort with an error if any (weekday, category) pair has zero usable stubs.

## 3. Per-date generation loop

**Always sequential, never parallel.** Process dates one at a time in chronological order. Do NOT dispatch per-date subagents and do NOT call multiple `web_search`/`web_fetch` operations concurrently. A 30-date batch will take a long wall-clock time; that is fine - this skill runs once a month from `/schedule` cron, not interactively. Parallel agents hit account-level token caps mid-bucket and the parent ends up filling the gap anyway.

For each `date_iso` in `dates_to_generate` (in ascending date order):

### 3.1 Pick category

```python
weekday = datetime.fromisoformat(date_iso).strftime("%A").lower()
candidates = day_map[weekday]
rng_cat = seeded_rng_for_date(date_iso, salt="category")
category = rng_cat.choice(candidates)
```

### 3.2 Pick stub

```python
rng_stub = seeded_rng_for_date(date_iso, salt="stub")
all_stubs = bank[category]
available = [s for s in all_stubs if s not in used_stubs]
if not available:
    # try the next candidate category
    continue_with_next_category = True
else:
    stub = rng_stub.choice(available)
```

If every candidate category for this weekday has no available stub, mark the entry `GENERATION_FAILED` with reason `"no usable stub in any candidate category"` and continue to the next date.

### 3.3 Generate body

Issue the prompt described in `references/system-prompt.md`. The model uses `web_search_20260209` and `web_fetch_20260209` to:

- Find 2-3 peer-reviewed studies that bear directly on the stub.
- Read the full text (PMC / open journal / arxiv) of 1-2.
- Write the passage in the format defined by the system prompt.
- Capture, for each cited paper, a 50-100 word **supporting passage** quoted verbatim from the fetched text.

The model returns:

```yaml
body: |
  <full email body, plain text>
references:
  - url: "..."
    title: "..."
    authors: "..."
    year: 2024
    published_at: "2024-08"
    supporting_passage: |
      <50-100 word direct quote>
```

### 3.4 Verify references

Run `python -m scripts.reference_verifier --urls-from-stdin` against the URL list extracted from the generated body. Each URL must return HTTP 200 (or another 2xx) on a HEAD request. Reject any non-`http(s)` scheme.

If any URL fails:
- Send a feedback turn instructing the model to re-search and rewrite using only verified URLs, AND reminding it to re-capture a `supporting_passage` for each new citation.
- Re-verify. If still failing, set status `GENERATION_FAILED` with reason `"reference verification failed: <urls>"`.

### 3.5 Build subject and write entry

```python
subject = f"{{NUDGE_SUBJECT_PREFIX}}{date_iso} - {category}: {stub}"
entry = {
  "status": "GENERATED",
  "category": category,
  "stub": stub,
  "subject": subject,
  "body": body,
  "references": [...],
  "generated_at": now_utc_iso(),
  "generator_model": "<model name>",
  "generator_session": "<session tag>",
}
python -m scripts.write_entry --entries-dir $ENTR --date $DATE_ISO --entry-json '<json>'
```

`write_entry.py` performs an **atomic merge**: it loads the existing `entries/YYYY-MM.yaml`, sets the key for `date_iso`, and writes the file back with `yaml.safe_dump`. Existing entries for other dates in the file are preserved.

### 3.6 Update in-memory used-history

```python
used_stubs.append(stub)
for ref in entry["references"]:
    used_urls.add(ref["url"])
```

So that subsequent dates in the same batch dedup against entries created earlier in the batch.

## 4. Render summary email

Run `python -m scripts.render_summary_email --entries-dir $ENTR --range $START..$END --used-history-as-of $TODAY > /tmp/summary.txt`.

The script produces a TL;DR bullet summary followed by a richer per-date report that flags:

- `[NEW]` where the cited paper was published in the last 90 days.
- `[FIRST]` where this is the first time this paper has appeared in any entry.
- `[FAILED]` for `GENERATION_FAILED` entries.

## 5. Send summary email

Run `python -m scripts.send_summary_email --body /tmp/summary.txt --subject "{{SUMMARY_SUBJECT_PREFIX}}$START..$END"`.

The script:
- Re-checks recipient = `{{ALLOWED_RECIPIENT}}` exactly. Aborts if not.
- Re-checks the subject prefix `{{SUMMARY_SUBJECT_PREFIX}}`. Aborts if not.
- SMTP-sends via Gmail App Password.

This send is exempt from any in-conversation confirmation rule the host environment normally requires - the recipient lock is the safety mechanism.

## 6. Commit and push

```bash
cd {{REPO_ROOT}}
git add entries/
git commit -m "$(cat <<'EOF'
feat: add sleep-nudge entries for <range>

<N> generated, <M> failed.

{{COMMIT_SUFFIX}}
EOF
)"
git push origin main
```
