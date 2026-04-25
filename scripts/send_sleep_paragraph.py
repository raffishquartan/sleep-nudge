"""Generate a sleep-science paragraph via Claude and email it."""

from __future__ import annotations

import argparse
import os
import random
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from scripts.topic_picker import (
    build_subject,
    load_day_categories,
    load_state,
    load_topic_bank,
    pick_category,
    pick_stub,
    save_state,
    update_state,
    validate_bank,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Call the LLM and print the rendered email; skip SMTP and skip state write.",
    )
    mode.add_argument(
        "--show-pick",
        action="store_true",
        help="Print the chosen category, stub, and proposed subject; skip LLM, SMTP, state write.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"

    day_map = load_day_categories(data_dir / "day-categories.yaml")
    bank = load_topic_bank(data_dir / "topic-bank.yaml")
    validate_bank(day_map, bank)
    state = load_state(data_dir / "state.json")

    now = datetime.now(timezone.utc)
    today_iso = now.strftime("%Y-%m-%d")
    weekday = now.strftime("%A").lower()

    rng = random.Random()
    category = pick_category(weekday, day_map, rng)
    stub = pick_stub(category, bank, state, rng)
    subject = build_subject(today_iso, category, stub)

    if args.show_pick:
        print(f"Weekday: {weekday}")
        print(f"Candidate categories: {day_map[weekday]}")
        print(f"Chosen category: {category}")
        print(f"Chosen stub: {stub}")
        print(f"Proposed subject: {subject}")
        print(f"State window size: {len(state)} entries (max 30)")
        return

    import anthropic

    system_prompt = (repo_root / "prompts" / "system-prompt.txt").read_text()
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL") or "claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Tonight's topic stub (use this exact narrow topic): {stub}. "
                    f"Category: {category}."
                ),
            }
        ],
    )
    body = next(block.text for block in response.content if block.type == "text")

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"Subject: {subject}")
        print(f"Category: {category}")
        print(f"Stub: {stub}")
        print(f"State (current): {len(state)} entries")
        print(f"State (proposed): {len(update_state(state, stub))} entries")
        print("--- BODY ---")
        print(body)
        print("=== END DRY RUN ===")
        return

    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient_address = os.environ["RECIPIENT_ADDRESS"]

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = recipient_address

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.send_message(msg)

    save_state(data_dir / "state.json", update_state(state, stub))
    print(f"Email sent to {recipient_address} (category={category}, stub={stub!r})")


if __name__ == "__main__":
    main()
