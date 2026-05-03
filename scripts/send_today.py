"""Daily mailman: read today's precomputed entry from entries/YYYY-MM.yaml and SMTP-send it.

No LLM calls. No web fetches. Just YAML lookup + Gmail SMTP.
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import yaml

DEFAULT_BUFFER_THRESHOLD = 7


@dataclass
class BufferStatus:
    future_count: int
    threshold: int
    is_low: bool


@dataclass
class RenderedEmail:
    subject: str
    body: str


@dataclass
class DispatchPlan:
    emails: list["RenderedEmail"]
    exit_code: int


def find_entry(entries_dir: Path, date_iso: str) -> dict | None:
    month = date_iso[:7]
    path = entries_dir / f"{month}.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text()) or {}
    return data.get(date_iso)


def count_future_entries(entries_dir: Path, today_iso: str) -> int:
    if not entries_dir.exists():
        return 0
    count = 0
    for path in entries_dir.glob("*.yaml"):
        data = yaml.safe_load(path.read_text()) or {}
        for date_iso, entry in data.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("status") != "GENERATED":
                continue
            if date_iso >= today_iso:
                count += 1
    return count


def render_email(entry: dict, date_iso: str) -> RenderedEmail:
    return RenderedEmail(subject=entry["subject"], body=entry["body"])


def build_overdue_alert_email(date_iso: str, reason: str) -> RenderedEmail:
    subject = f"[Cld] Sleep Nudge OVERDUE - {date_iso}"
    body = (
        f"No sleep nudge entry could be sent for {date_iso}.\n\n"
        f"Reason: {reason}\n\n"
        "Generation has fallen behind. Run /generate-sleep-nudges to refill the buffer.\n"
    )
    return RenderedEmail(subject=subject, body=body)


def decide_dispatch(
    entries_dir: Path, today_iso: str, *, buffer_threshold: int
) -> DispatchPlan:
    emails: list[RenderedEmail] = []
    exit_code = 0

    entry = find_entry(entries_dir, today_iso)
    sent_overdue = False
    if entry is None:
        emails.append(
            build_overdue_alert_email(today_iso, reason="No entry found in entries/*.yaml")
        )
        exit_code = 1
        sent_overdue = True
    elif entry.get("status") == "GENERATION_FAILED":
        reason = entry.get("failure_reason", "unknown")
        emails.append(
            build_overdue_alert_email(
                today_iso, reason=f"Entry status=GENERATION_FAILED: {reason}"
            )
        )
        exit_code = 1
        sent_overdue = True
    else:
        emails.append(render_email(entry, today_iso))

    if not sent_overdue:
        future_count = count_future_entries(entries_dir, today_iso)
        if future_count < buffer_threshold:
            buffer = BufferStatus(
                future_count=future_count, threshold=buffer_threshold, is_low=True
            )
            emails.append(build_buffer_alert_email(today_iso, buffer))
            exit_code = 1

    return DispatchPlan(emails=emails, exit_code=exit_code)


def build_buffer_alert_email(today_iso: str, buffer: BufferStatus) -> RenderedEmail:
    subject = f"[Cld] Sleep Nudge BUFFER LOW - {buffer.future_count} days remaining"
    body = (
        f"As of {today_iso}, only {buffer.future_count} future-dated GENERATED entries "
        f"remain (threshold: {buffer.threshold}).\n\n"
        "Run /generate-sleep-nudges to top up the buffer before it runs out.\n"
    )
    return RenderedEmail(subject=subject, body=body)


def smtp_send(rendered: RenderedEmail, gmail_address: str, app_password: str, recipient: str) -> None:
    msg = MIMEText(rendered.body)
    msg["Subject"] = rendered.subject
    msg["From"] = gmail_address
    msg["To"] = recipient
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, app_password)
        server.send_message(msg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the dispatch plan without sending email.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Override today's date (YYYY-MM-DD). Default: now() in UTC.",
    )
    parser.add_argument(
        "--buffer-threshold",
        type=int,
        default=DEFAULT_BUFFER_THRESHOLD,
        help=f"Buffer warning threshold in days (default: {DEFAULT_BUFFER_THRESHOLD}).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    entries_dir = repo_root / "entries"

    today_iso = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    plan = decide_dispatch(entries_dir, today_iso, buffer_threshold=args.buffer_threshold)

    if args.dry_run:
        print(f"=== DRY RUN for {today_iso} ===")
        print(f"Exit code: {plan.exit_code}")
        for i, email in enumerate(plan.emails, 1):
            print(f"--- Email {i} ---")
            print(f"Subject: {email.subject}")
            print(email.body)
        return

    gmail_address = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_ADDRESS"]

    for email in plan.emails:
        smtp_send(email, gmail_address, app_password, recipient)
        print(f"Sent: {email.subject}")

    sys.exit(plan.exit_code)


if __name__ == "__main__":
    main()
