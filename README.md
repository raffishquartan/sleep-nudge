# Sleep Nudge

A GitHub Actions workflow that runs daily at 22:00 UTC, calls the Anthropic API (Claude Haiku 4.5) to generate one evidence-based sleep paragraph, and emails it to you via Gmail SMTP.

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

## Available models

| Model | ID | Input $/1M | Output $/1M | Est. monthly cost |
|---|---|---|---|---|
| Haiku 4.5 (default) | `claude-haiku-4-5-20251001` | $1.00 | $5.00 | ~$0.08 |
| Sonnet 4.6 | `claude-sonnet-4-6` | $3.00 | $15.00 | ~$0.24 |
| Opus 4.6 | `claude-opus-4-6` | $5.00 | $25.00 | ~$0.40 |

## Cost

~$0.08/month with Haiku (default). GitHub Actions: free.
