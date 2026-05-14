---
name: generate-sleep-nudges
description: Pre-generate the next N days of evidence-based sleep-science nudges into the sleep-nudge repo's entries/YYYY-MM.yaml files, using web_search + web_fetch for citation grounding. Use when the user says "generate sleep nudges", "fill the sleep nudge buffer", "/generate-sleep-nudges", or when a buffer-low alert email arrives. Works on the model's subscription (no API spend) so the daily mailman GitHub Action can stay free.
---

# generate-sleep-nudges

## Purpose

The sleep-nudge GitHub Actions workflow sends one short, evidence-grounded sleep-science email per day. This skill batch-generates the next N days of those entries into committed YAML files, so the daily mailman just needs to look up "today" and SMTP-send. Cost discipline: this is the only place that runs the expensive grounded-generation loop, and it runs on the user's Claude subscription rather than the API.

## When to use

- The user invokes `/generate-sleep-nudges` (with or without arguments).
- A `BUFFER LOW` alert email or hook reminder arrives.
- An `OVERDUE` alert email arrives (the buffer has run dry; generation has fallen behind).
- A scheduled cron (created via `/schedule`) fires this skill.

## Cadence (for the human)

Recommended: run once a month, around day 25 of the calendar month, with no arguments. That generates the next 30 days, comfortably ahead of the daily mailman's needs.

Three robust ways to make that happen, in increasing autonomy:

1. **Manual.** Run `/generate-sleep-nudges` whenever you feel like it. The daily mailman will email you `BUFFER LOW` 7 days before it runs out, and `OVERDUE` if it does run out. Both alerts include the action prompt.
2. **`/schedule` cron (recommended).** In any Claude Code session, run `/schedule` and create a recurring routine: cron `0 9 25 * *` (09:00 UTC on day-of-month 25), prompt = `/generate-sleep-nudges`. Runs in Anthropic's cloud, laptop-off works.
3. **`/loop` poll.** If `/schedule` is unavailable for any reason, `/loop 30d /generate-sleep-nudges` works but requires a Claude Code session to be running.

If `BUFFER LOW` or `OVERDUE` arrives unexpectedly, run `/generate-sleep-nudges` immediately - the buffer is the safety net, alerts mean it has frayed.

## Inputs

The skill accepts an optional **range argument**:

| Argument | Meaning |
|---|---|
| (none) | Generate the next 30 calendar days starting from `today + buffered_count` (avoids duplicating existing future-dated entries). |
| `2026-06` | Generate every date in that calendar month (overwrites only `GENERATION_FAILED` entries; skips existing `GENERATED` entries unless `--force` is also given). |
| `2026-05-15..2026-05-22` | Generate that specific date range. |
| `2026-05-15` | Generate exactly that single date. |
| `--force` | Overwrite existing entries even if they are `GENERATED`. Use sparingly. |

## Repo paths

```
REPO  = {{REPO_ROOT}}
DATA  = $REPO/data
ENTR  = $REPO/entries
```

## High-level algorithm

Read `references/algorithm.md` for the full step-by-step. The short version:

1. Resolve which dates to generate. Skip dates that already have `GENERATED` entries unless `--force`.
2. Build the **used-history context**: for each date to generate, the prior 90 days of stubs and cited URLs (from the entries themselves).
3. For each date in chronological order:
   1. Pick category deterministically with `seeded_rng_for_date(date_iso, salt="category")` against `data/day-categories.yaml`.
   2. Pick stub deterministically with `seeded_rng_for_date(date_iso, salt="stub")` against `data/topic-bank.yaml`, excluding stubs in the 90-day window.
   3. Generate the body using `web_search` + `web_fetch` per `references/system-prompt.md`. Capture each cited paper's **supporting passage** (50-100 word direct quote that grounds the central claim).
   4. Verify every cited URL using `scripts/reference_verifier.py`. One retry on failure; mark `GENERATION_FAILED` if still failing.
   5. Write the entry into `entries/YYYY-MM.yaml` via `scripts/write_entry.py`.
   6. Append the new stub and URLs to the in-memory used-history so subsequent dates in the same batch see them.
4. Once all dates are written, run `scripts/render_summary_email.py` to build the TL;DR + rich summary email.
5. Auto-send the summary via Gmail SMTP using `scripts/send_summary_email.py`. The recipient is hardcoded to `{{ALLOWED_RECIPIENT}}` and the script defensively re-checks before sending.
6. Stage and commit the new entries (`git add entries/ && git commit -m "..." && git push`). If `{{COMMIT_SUFFIX}}` is non-empty, append it to the commit message.

## Entry schema

```yaml
"2026-05-15":
  status: GENERATED          # or GENERATION_FAILED
  category: metabolic
  stub: "insulin sensitivity reduction after partial sleep restriction"
  subject: "{{NUDGE_SUBJECT_PREFIX}}2026-05-15 - metabolic: insulin sensitivity..."
  body: |
    <full plain-text email body, including References section and trailing --->
  references:
    - url: "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC..."
      title: "Title of paper"
      authors: "Author A, Author B et al."
      year: 2024
      published_at: "2024-08"           # YYYY or YYYY-MM
      verified_at: "2026-05-02T03:11:00Z"
      verified_status: 200
      supporting_passage: |
        Direct quote from the paper that grounds the central claim, 50-100 words.
  generated_at: "2026-05-02T03:11:00Z"
  generator_model: "claude-opus-4-7"
  generator_session: "20260502-skill-tag"
```

For `GENERATION_FAILED`:

```yaml
"2026-05-16":
  status: GENERATION_FAILED
  category: cognitive
  stub: "REM-mediated emotional memory reconsolidation"
  failure_reason: "All 3 cited URLs returned 404 after retry"
  generated_at: "2026-05-02T03:11:00Z"
```

## Quality bars

These are non-negotiable. The skill's value is exactly proportional to how strictly they hold.

- **Citation truthfulness.** Every factual claim must be grounded in a paper the skill has actually `web_fetch`ed in this turn. The `supporting_passage` field is the audit trail - if you cannot extract a 50-100 word passage that demonstrably supports the claim, drop the claim.
- **Mechanistic depth.** Explain biology / neural mechanism, not just outcomes. A paragraph that just restates an abstract is rejected.
- **Topical novelty.** No stub may have been used in the prior 90 days. **Also avoid re-citing the same paper** (URL match) as another entry in the prior 90 days, even if the stub is different.
- **Recency awareness.** When generating, the skill should preferentially surface papers published in the last 90 days where they exist - the summary email flags these as `[NEW]`.
- **Robustness to gaps.** If generation cannot succeed for a date, mark it `GENERATION_FAILED` rather than skipping silently. The daily mailman will emit an `OVERDUE` alert when the date arrives.

## Failure modes

- **No usable stubs in the chosen category** (everything in last 90 days): pick a different category candidate from the day's list. If all candidates are exhausted, mark `GENERATION_FAILED` with reason `no usable stub in any candidate category`.
- **Reference verification fails after retry**: mark `GENERATION_FAILED` with reason `reference verification failed: <urls>`.
- **Tool timeout / pause_turn never resolves**: retry once, then `GENERATION_FAILED`.

## Execution model: sequential, never parallel

This skill is **always run sequentially in the parent session**. Do NOT dispatch per-date subagents and do NOT attempt to parallelise generation.

Reasoning:

- Parallel agents hit account-level token-budget caps mid-bucket, leaving most dates ungenerated and forcing the parent to fill the gap anyway.
- A sequential 30-date run takes a long wall-clock time but is reliable, predictable, and cheaper end-to-end (no per-agent prompt context overhead).
- Long wall-clock time is acceptable - this skill runs once a month from `/schedule` cron, not interactively, so latency does not matter.

Never modify `data/topic-bank.yaml` or `data/day-categories.yaml` from inside this skill. Bank changes are an explicit, separate user action.
