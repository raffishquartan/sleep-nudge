# Sleep Nudge

A GitHub Actions workflow that runs daily at 22:00 UTC, picks a curated topic stub, calls the Anthropic API (Claude Sonnet 4.6 by default) with web_search and web_fetch tools to generate a tool-grounded sleep paragraph, verifies the cited URLs resolve, and emails it via Gmail SMTP.

## Setup

1. **Gmail App Password**: Enable 2-Step Verification, then create an App Password at https://myaccount.google.com/apppasswords
2. **Add GitHub Secrets** (`Settings > Secrets and variables > Actions`):
   - `ANTHROPIC_API_KEY` - your Anthropic API key
   - `GMAIL_ADDRESS` - the dedicated sender Gmail address
   - `GMAIL_APP_PASSWORD` - the sender account's 16-character App Password
   - `RECIPIENT_ADDRESS` - your personal email (where you want to receive the nudge)
3. **Optionally set the model** (`Settings > Secrets and variables > Actions > Variables`):
   - `CLAUDE_MODEL` - model ID to use (defaults to `claude-sonnet-4-6`)
4. **Test**: Go to Actions tab, select "Sleep Paragraph", click "Run workflow"

## How it picks topics

Three data files in `data/` drive the topic picker:

- `data/day-categories.yaml` - day of week -> 2-3 candidate categories. Saturday's candidates differ from Tuesday's so the weekly mix stays varied.
- `data/topic-bank.yaml` - 11 categories (cardiovascular, metabolic, cognitive, emotional, immune, hormonal, neurological, gut, recovery, pain, sensory) with ~30 mechanistically distinct stubs each (~330 total). Glymphatic and memory-consolidation are deliberately capped at 3 stubs each.
- `data/state.json` - rolling window of the last 30 used stubs.

Each run:

1. Reads today's weekday, picks one category uniformly at random from that day's candidates.
2. Picks one stub uniformly at random from the chosen category, excluding stubs in `state.json`. Falls back to the full category if every stub has been used.
3. Calls Claude with `web_search_20260209` and `web_fetch_20260209` tools, telling it to ground every claim in fetched papers.
4. Parses the references in the response and HTTP-checks each cited URL.
5. If any reference fails to resolve, sends a feedback turn asking the model to rewrite using verified sources only. Aborts after one retry rather than emailing unverified citations.
6. Builds the subject line: `[Cld] Sleep Nudge - YYYY-MM-DD - <category>: <stub>`.
7. Sends the email via Gmail SMTP.
8. Appends the new stub to `state.json` and commits it back to the repo.

## Grounding (no-hallucination guard)

The system prompt instructs the model to:

- Use web_search and web_fetch to retrieve actual full text (PMC / journal open access / arxiv).
- Read the methods and conclusions, not just the abstract.
- Cite only papers it has fetched in this turn; if a fetched paper turns out not to support the claim, drop the claim or find a different one.
- Prefer a shorter paragraph with verified citations over a longer one with fabricated citations.
- If nothing can be grounded, write the paragraph with no references and an explicit "References: none verified" line.

After generation, `scripts/reference_verifier.py` parses the References section and HTTP-HEAD-checks each URL. Failures trigger one retry with feedback; if still failing, the workflow aborts the send rather than emailing bad citations.

The verifier rejects any URL whose scheme is not `http` or `https` (CWE-939 guard against an LLM-emitted `file://` URL).

## State commits

The workflow commits the updated `state.json` after each successful send. The commit author is `github-actions[bot]` and the message contains `[skip ci]` so the push does not retrigger the workflow. The job declares `permissions: contents: write` so the default `GITHUB_TOKEN` can push without a PAT. A `concurrency` group serialises rapid-fire `workflow_dispatch` triggers so they cannot race each other when pushing.

## Local dry-run

Two flags let you verify the picker and the wiring locally without sending an email.

`--show-pick` runs the picker and prints what it would do. No LLM call, no SMTP, no state write. Works without an API key:

```bash
python -m scripts.send_sleep_paragraph --show-pick
```

`--dry-run` calls Claude end-to-end (web tools + verifier retry loop) and prints the rendered email, but skips SMTP and skips the state write. Needs `ANTHROPIC_API_KEY` set:

```bash
ANTHROPIC_API_KEY=<key> python -m scripts.send_sleep_paragraph --dry-run
```

## Tests

Unit tests cover the picker primitives and the reference verifier (parser, HTTP check, file:// rejection):

```bash
python -m pytest tests/ -v
```

## Available models and estimated cost

Tool-grounded generation uses substantially more tokens per run than the previous untooled design - each run loads the full text of 1-2 PMC papers (~30-60k input tokens) into the model's context so the LLM can ground every claim.

**Per-run token model** (used to derive the table below):
- System + user + tool defs: ~1.5k input tokens
- 2 web_search calls -> result blocks: ~6k input tokens
- 1-2 web_fetch calls of full PMC papers: ~30-60k input tokens
- Adaptive thinking + final output: 2-4k output tokens
- ~2 web_search fees at $0.01/search: ~$0.02

| Model | ID | Input $/1M | Output $/1M | Per-run | Est. monthly (30 sends) |
|---|---|---|---|---|---|
| Sonnet 4.6 (default) | `claude-sonnet-4-6` | $3.00 | $15.00 | $0.20 - $0.32 | **~$6 - $10** |
| Opus 4.6 | `claude-opus-4-6` | $5.00 | $25.00 | $0.32 - $0.52 | ~$10 - $16 |
| Opus 4.7 | `claude-opus-4-7` | $5.00 | $25.00 | $0.32 - $0.55 | ~$10 - $16 |
| Haiku 4.5 | `claude-haiku-4-5-20251001` | $1.00 | $5.00 | $0.07 - $0.11 | ~$2 - $3 (NOT recommended - lower citation quality with tool use) |

The biggest variance driver is how much full-text `web_fetch` the model decides to do. Opus 4.7's stronger literal instruction following may produce shorter outputs than Opus 4.6 on this task, so the upper bound for 4.7 may overshoot in practice. If the verifier triggers a retry (rare with grounding), double that single run. Budget for the upper end and review actual spend after 2-3 weeks of real sends. GitHub Actions remains free.
