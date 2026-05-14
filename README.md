# Sleep Nudge

A daily, evidence-grounded nudge in your inbox reminding you why sleep matters - so you go to bed instead of spending another night commanding Claude Code like the admiral of a fleet.

Each nudge is a short passage of peer-reviewed sleep science: one specific mechanism (cardiovascular, metabolic, cognitive, emotional, hormonal...), one or two real papers with verified URLs and verbatim supporting quotes, no fluff. The expensive generation step runs on your Claude subscription once a month, so the daily email runs as a free GitHub Action at $0 in API spend.

## How it works

1. Once a month a Claude Code skill (`generate-sleep-nudges`) batch-generates ~30 days of nudges by searching, fetching and reading peer-reviewed papers, then committing the results to `entries/YYYY-MM.yaml`.
2. Each day at the configured time a free GitHub Action looks up today's pre-generated entry and SMTP-sends it via your Gmail account.
3. If the buffer of pre-generated entries ever runs low or runs out, the daily action emails you a warning so you can trigger the next regeneration.

## Dependencies

- A Gmail account you are happy to send automated email from (you'll create an App Password for it, so 2-Step Verification needs to be enabled).
- A Claude Code subscription (Pro or Max). Generation uses `web_search` + `web_fetch` and is cost-effective on a subscription; using the API directly would cost ~$6-$10/month.
- A GitHub account. The daily mailman runs as a free GitHub Action under your fork.

## Setup

### 1. Fork and clone

Fork this repository to your GitHub account, then clone your fork locally:

```bash
git clone git@github.com:<your-username>/sleep-nudge.git
cd sleep-nudge
```

### 2. Install the generation skill

Run the install script and answer the prompts:

```bash
./install.sh
```

You'll be asked for:

| Prompt | What to enter |
|---|---|
| `REPO_ROOT` | Absolute path to your local clone (defaults to the current directory). |
| `ALLOWED_RECIPIENT` | The Gmail address where the daily nudge and the post-generation summary should land. |
| `ALLOWED_SENDER` | The Gmail address that will send the email (the account whose App Password you'll set up in step 3). |
| `SUMMARY_SUBJECT_PREFIX` | Subject prefix for the post-generation summary email. Default `"Sleep Nudge generation summary "`. |
| `NUDGE_SUBJECT_PREFIX` | Subject prefix for the daily nudge emails. Default `"Sleep Nudge - "`. |
| `COMMIT_SUFFIX` | Optional trailing line for any git commit messages the skill makes (leave blank for none). |

The script renders the templated skill bundle and writes it to `~/.claude/skills/generate-sleep-nudges/` (override with `./install.sh --target /custom/path`). It's idempotent - re-running prompts again with your previous answers as defaults.

### 3. Create a Gmail App Password

Go to <https://myaccount.google.com/apppasswords> (requires 2-Step Verification on the sender account) and generate a 16-character App Password labelled `sleep-nudge`. Keep it handy for step 4.

### 4. Configure GitHub Secrets

In your fork's GitHub settings, go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `GMAIL_ADDRESS` | The sender Gmail address from step 2. |
| `GMAIL_APP_PASSWORD` | The 16-character App Password from step 3. |
| `RECIPIENT_ADDRESS` | The recipient Gmail address from step 2. |

### 5. Test the daily mailman

In your fork, go to **Actions → Send Today → Run workflow**. Within a minute or two you should receive either today's nudge (if you've already generated entries) or an `OVERDUE` alert (if you haven't - expected on first setup).

### 6. Generate the buffer

In any Claude Code session, invoke:

```
/generate-sleep-nudges
```

The skill walks the algorithm in `~/.claude/skills/generate-sleep-nudges/references/algorithm.md`. A first-time run generates 30 days of nudges and takes ~1 hour of wall-clock time. When it finishes you'll receive a summary email and the entries will be committed to `entries/YYYY-MM.yaml`. Push that commit.

### 7. Schedule monthly regeneration (optional but recommended)

In Claude Code, run `/schedule` and create a routine:

- Cron: `0 9 25 * *` (09:00 UTC on day-of-month 25)
- Prompt: `/generate-sleep-nudges`

This runs in Anthropic's cloud, so your laptop being off doesn't matter. If you don't set this up, you'll get a `BUFFER LOW` email 7 days before the buffer runs out, and an `OVERDUE` email if it runs out entirely - both prompt you to run `/generate-sleep-nudges` manually.

## Daily mailman behaviour

`scripts/send_today.py` makes three decisions:

| Today's entry | Buffer (future `GENERATED` entries) | Effect |
|---|---|---|
| `GENERATED` | >= 7 | Send the nudge. Exit 0. |
| `GENERATED` | < 7 | Send the nudge AND a `BUFFER LOW` warning email. Exit 1 (action goes red). |
| `GENERATION_FAILED` or missing | (any) | Send an `OVERDUE` alert with the reason. Exit 1. |

The non-zero exit makes the GitHub Action turn red on alert paths so you also see the failure in your inbox via GitHub's notifications.

## Topic picker

The picker decides what each daily nudge is about:

- `data/day-categories.yaml` maps each weekday to candidate categories (Monday → cardiovascular, immune, hormonal; Tuesday → metabolic, cognitive, emotional; ... and so on).
- `data/topic-bank.yaml` holds ~30 specific stubs per category (e.g. `"Habitual late bedtime and exaggerated morning blood pressure surge"` under `cardiovascular`).
- `scripts/topic_picker.py` exposes a deterministic date-seeded RNG so that re-running generation for the same date with the same prior-used-stubs context picks the same `(category, stub)` pair.
- A 90-day rolling exclusion window (built at generation time from existing entries) blocks stub reuse and discourages re-citing the same paper, even across different stubs.

## Generation skill

The bulk generation logic lives in `skills/generate-sleep-nudges/`. After running `./install.sh` it sits in your Claude Code skills directory and activates when you type `/generate-sleep-nudges`.

- `SKILL.md` - the model-facing description: when to use it, cadence, inputs, entry schema, quality bars.
- `references/algorithm.md` - the per-run algorithm the model walks through.
- `references/system-prompt.md` - the prompt each per-date generation issues to itself.
- `scripts/` - Python helpers for verifying URLs, building used-history, writing entries atomically, rendering the summary email, and sending it via SMTP.
- `tests/` - pytest suite for the helpers. Run with `cd skills/generate-sleep-nudges && python -m pytest tests/ -v`.

## Tests

```bash
python -m pytest tests/ -v
```

This covers the daily-mailman and topic-picker logic. The skill has its own test suite under `skills/generate-sleep-nudges/tests/`.

## Local dry-run

```bash
python -m scripts.send_today --dry-run --date 2026-05-15 --buffer-threshold 7
```

Reads `entries/2026-05.yaml`, builds the dispatch plan (today's nudge and/or alert emails), prints subjects and bodies, and sends nothing.

## Disclaimer

The nudges this repository emits are summaries of peer-reviewed sleep-science research, not medical advice. If you have a sleep problem that concerns you, talk to a clinician.
