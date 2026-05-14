"""Send the post-generation summary email via Gmail SMTP.

Defensive recipient/sender re-check enforces the auto-send safety property: the script
aborts (no send) if the configured recipient/sender/subject-prefix don't match exactly.
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

ALLOWED_RECIPIENT = "{{ALLOWED_RECIPIENT}}"
ALLOWED_SENDER = "{{ALLOWED_SENDER}}"
REQUIRED_SUBJECT_PREFIX = "{{SUMMARY_SUBJECT_PREFIX}}"


def assert_send_allowed(*, recipient: str, sender: str, subject: str) -> None:
    if recipient != ALLOWED_RECIPIENT:
        raise SystemExit(f"ABORT: recipient {recipient!r} != {ALLOWED_RECIPIENT!r}")
    if sender != ALLOWED_SENDER:
        raise SystemExit(f"ABORT: sender {sender!r} != {ALLOWED_SENDER!r}")
    if not subject.startswith(REQUIRED_SUBJECT_PREFIX):
        raise SystemExit(
            f"ABORT: subject must start with {REQUIRED_SUBJECT_PREFIX!r}; got {subject!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", type=Path, required=True, help="Path to body text file.")
    parser.add_argument("--subject", required=True)
    args = parser.parse_args()

    sender = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("SUMMARY_RECIPIENT", ALLOWED_RECIPIENT)

    assert_send_allowed(recipient=recipient, sender=sender, subject=args.subject)

    body_text = args.body.read_text()
    msg = MIMEText(body_text)
    msg["Subject"] = args.subject
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, app_password)
        server.send_message(msg)

    print(f"Sent summary to {recipient}", file=sys.stderr)


if __name__ == "__main__":
    main()
