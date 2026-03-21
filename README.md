# Sleep Nudge

A GitHub Actions workflow that runs daily at 22:00 UTC, calls the Anthropic API (Claude Haiku 4.5) to generate one evidence-based sleep paragraph, and emails it to you via Gmail SMTP.

## Setup

1. **Gmail App Password**: Enable 2-Step Verification, then create an App Password at https://myaccount.google.com/apppasswords
2. **Add GitHub Secrets** (`Settings > Secrets and variables > Actions`):
   - `ANTHROPIC_API_KEY` - your Anthropic API key
   - `GMAIL_ADDRESS` - your Gmail address (sender and recipient)
   - `GMAIL_APP_PASSWORD` - the 16-character App Password
3. **Test**: Go to Actions tab, select "Sleep Paragraph", click "Run workflow"

## Cost

~$0.08/month (Anthropic API). GitHub Actions: free.
