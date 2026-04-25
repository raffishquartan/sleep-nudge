# Sleep Nudge

A GitHub Actions workflow that runs daily at 22:00 UTC, picks a curated topic stub, calls the Anthropic API (Claude Haiku 4.5) to generate one evidence-based sleep paragraph on that exact topic, and emails it via Gmail SMTP.

## Setup

1. **Gmail App Password**: Enable 2-Step Verification, then create an App Password at https://myaccount.google.com/apppasswords
2. **Add GitHub Secrets** (`Settings > Secrets and variables > Actions`):
   - `ANTHROPIC_API_KEY` - your Anthropic API key
   - `GMAIL_ADDRESS` - the dedicated sender Gmail address
   - `GMAIL_APP_PASSWORD` - the sender account's 16-character App Password
   - `RECIPIENT_ADDRESS` - your personal email (where you want to receive the nudge)
3. **Optionally set the model** (`Settings > Secrets and variables > Actions > Variables`):
   - `CLAUDE_MODEL` - model ID to use (defaults to `claude-haiku-4-5-20251001`)
4. **Test**: Go to Actions tab, select "Sleep Paragraph", click "Run workflow"

## How it picks topics

Three data files in `data/` drive the topic picker:

- `data/day-categories.yaml` - day of week -> 2-3 candidate categories. Saturday's candidates differ from Tuesday's so the weekly mix stays varied.
- `data/topic-bank.yaml` - 11 categories (cardiovascular, metabolic, cognitive, emotional, immune, hormonal, neurological, gut, recovery, pain, sensory) with ~30 mechanistically distinct stubs each (~330 total). Glymphatic and memory-consolidation are deliberately capped at 3 stubs each because they were over-represented before this redesign.
- `data/state.json` - rolling window of the last 30 used stubs.

Each run:

1. Reads today's weekday, picks one category uniformly at random from that day's candidates.
2. Picks one stub uniformly at random from the chosen category, excluding stubs that appear in `state.json`. Falls back to the full category if every stub has been used.
3. Passes the chosen stub to Claude in the user message; the system prompt is unchanged.
4. Builds the subject line: `[Cld] Sleep Nudge - YYYY-MM-DD - <category>: <stub>`.
5. Sends the email via Gmail SMTP.
6. Appends the new stub to `state.json` (trimming to the last 30) and commits it back to the repo.

## State commits

The workflow commits the updated `state.json` after each successful send. The commit author is `github-actions[bot]` and the message contains `[skip ci]` so the push does not retrigger the workflow. The job declares `permissions: contents: write` so the default `GITHUB_TOKEN` can push without a PAT.

## Local dry-run

Two flags let you verify the picker and the wiring locally without sending an email.

`--show-pick` runs the picker and prints what it would do. No LLM call, no SMTP, no state write. Works without an API key:

```bash
python -m scripts.send_sleep_paragraph --show-pick
```

`--dry-run` calls Claude end-to-end and prints the rendered email, but skips SMTP and skips the state write. Needs `ANTHROPIC_API_KEY` set:

```bash
ANTHROPIC_API_KEY=<key> python -m scripts.send_sleep_paragraph --dry-run
```

## Tests

Unit tests cover the picker primitives:

```bash
python -m pytest tests/ -v
```

## Available models

| Model | ID | Input $/1M | Output $/1M | Est. monthly cost |
|---|---|---|---|---|
| Haiku 4.5 (default) | `claude-haiku-4-5-20251001` | $1.00 | $5.00 | ~$0.08 |
| Sonnet 4.6 | `claude-sonnet-4-6` | $3.00 | $15.00 | ~$0.24 |
| Opus 4.6 | `claude-opus-4-6` | $5.00 | $25.00 | ~$0.40 |

## Cost

~$0.08/month with Haiku (default). GitHub Actions: free.
