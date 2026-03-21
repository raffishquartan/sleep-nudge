"""Generate a sleep-science paragraph via Claude and email it."""

import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import anthropic


def main():
    script_dir = Path(__file__).resolve().parent
    system_prompt = (script_dir.parent / "prompts" / "system-prompt.txt").read_text()

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": "Give me tonight's sleep paragraph."}],
    )

    body = next(block.text for block in response.content if block.type == "text")

    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    msg = MIMEText(body)
    msg["Subject"] = f"Sleep Nudge \u2014 {today}"
    msg["From"] = gmail_address
    msg["To"] = gmail_address

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.send_message(msg)

    print(f"Email sent to {gmail_address}")


if __name__ == "__main__":
    main()
