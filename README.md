# Sleep Nudge

A two-stage system for daily evidence-grounded sleep-science emails:

1. **Generation (offline, on subscription).** A Claude Code skill called `generate-sleep-nudges` (lives in `~/.claude/skills/generate-sleep-nudges/`, invoked manually as `/generate-sleep-nudges` or via a recurring `/schedule` cron) batch-generates ~30 days of nudges into committed `entries/YYYY-MM.yaml` files. Each entry holds a verified body, references with verbatim supporting passages, and metadata. Generation uses `web_search` + `web_fetch` and so runs on the subscription, not the API - keeping spend at $0/month.
2. **Daily send (free GitHub Action).** A daily cron at 22:00 UTC runs `scripts/send_today.py`, which looks up today's entry in `entries/YYYY-MM.yaml` and SMTP-sends the precomputed body. No LLM call, no token spend.

## Cost

Previous design (per-run web_search + web_fetch with Sonnet 4.6): ~$6-$10/month, ~194k input tokens per day. This design: ~$0/month for the daily send. Generation runs on the user's Claude subscription as a normal interactive or scheduled session.

## Setup

1. **Gmail App Password** at https://myaccount.google.com/apppasswords (requires 2-Step Verification).
2. **GitHub Secrets** (`Settings > Secrets and variables > Actions`):
   - `GMAIL_ADDRESS` - the sender Gmail address.
   - `GMAIL_APP_PASSWORD` - the sender's 16-character App Password.
   - `RECIPIENT_ADDRESS` - the personal email to receive the nudge.
   - The `ANTHROPIC_API_KEY` and `CLAUDE_MODEL` settings are no longer needed.
3. **Test the daily mailman**: Actions tab -> "Send Today" -> "Run workflow".
4. **Generate the buffer**: in Claude Code, run `/generate-sleep-nudges`. The skill walks the algorithm in `~/.claude/skills/generate-sleep-nudges/references/algorithm.md`.

## Daily mailman behaviour

`scripts/send_today.py` makes three decisions:

| Today's entry | Buffer (future GENERATED entries) | Effect |
|---|---|---|
| GENERATED | >= 7 | Send the nudge. Exit 0. |
| GENERATED | < 7 | Send the nudge AND a `BUFFER LOW` warning email. Exit 1 (action goes red). |
| GENERATION_FAILED or missing | (any) | Send an `OVERDUE` alert with the reason. Exit 1. |

The non-zero exit makes the GitHub Action turn red on alert paths so you also see the failure in your inbox via GitHub's notifications.

## Topic picker

The picker (`scripts/topic_picker.py`) is unchanged in spirit but adds a date-seeded RNG helper used by the generator skill so that re-running generation for a single date deterministically picks the same category and stub given the same prior-used-stubs context.

- `data/day-categories.yaml` - per-weekday category candidates.
- `data/topic-bank.yaml` - 11 categories x ~30 stubs.
- `seeded_rng_for_date(date_iso, salt)` - reproducible per-date RNG; `salt` separates category vs stub draws.

The 90-day rolling exclusion window (stubs from any entry in the last 90 days) is computed at generation time by `scripts/build_used_history.py` (in the skill bundle), reading entries directly. There is no `data/state.json` anymore.

## Tests

```bash
python -m pytest tests/ -v
```

The skill's own scripts are tested separately under `~/.claude/skills/generate-sleep-nudges/tests/`.

## Local dry-run

```bash
python -m scripts.send_today --dry-run --date 2026-05-15 --buffer-threshold 7
```

Reads `entries/2026-05.yaml`, builds the dispatch plan (entry email and/or alert emails), prints subjects + bodies, no SMTP.
