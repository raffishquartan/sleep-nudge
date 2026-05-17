# Setting up a monthly regeneration reminder

Share this file with Claude Code in any session and ask: **"Create the monthly routine described in this file."**

Claude Code will use the `/schedule` skill to create the routine and pick whatever notification method is available in your environment (email, calendar, Telegram, etc.).

---

## Prompt for Claude Code

Please create a cloud routine using the `/schedule` skill with these settings:

- **Cron:** `0 9 25 * *` (9 am on the 25th of each month, local time)
- **Recurring:** yes
- **Description:** Monthly reminder to regenerate the sleep nudge buffer

The routine prompt should be exactly:

> Remind me that it is time to run `/generate-sleep-nudges` in a local Claude Code session to pre-generate next month's sleep nudge entries. The generation must run locally (not here in the cloud) because it needs access to a cloned copy of the sleep-nudge repository and git credentials to push the results. Use the best notification method available to you — for example: send an email, add a calendar event, send a chat message, or any other tool you have configured. Keep it short: "Time to run /generate-sleep-nudges — your monthly sleep nudge buffer needs refilling. Run this in a local Claude Code session."

---

## Notes

- **Why local?** The monthly generation writes YAML files to a cloned git repository and pushes them to GitHub. That requires local git credentials. The cloud routine cannot do this — it only sends the reminder.
- **Built-in fallback:** Even without this routine, the daily GitHub Action emails you a `BUFFER LOW` warning when fewer than 7 entries remain (~day 23 of the cycle). That email is your backup prompt to regenerate.
- **Running the routine once instead:** After setting up the routine, you can also ask Claude Code to "run the monthly sleep nudge reminder routine now" to trigger it immediately and verify the notification arrives.
