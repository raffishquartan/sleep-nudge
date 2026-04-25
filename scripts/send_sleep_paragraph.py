"""Generate a tool-grounded sleep-science paragraph via Claude and email it."""

from __future__ import annotations

import argparse
import os
import random
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from scripts.reference_verifier import (
    all_passed,
    failure_summary,
    parse_references,
    verify_references,
)
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

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_VERIFY_RETRIES = 1


def build_user_message(stub: str, category: str) -> str:
    return (
        f"Tonight's topic stub (use this exact narrow topic): {stub}. "
        f"Category: {category}.\n\n"
        "Procedure (follow exactly):\n"
        "1. Use web_search to find 2-3 peer-reviewed studies that bear directly on this stub.\n"
        "2. Use web_fetch to retrieve the full text of the most directly relevant one or two "
        "(prefer PMC, journal open-access, or arxiv). Read the methods and the actual conclusions, "
        "not just the abstract.\n"
        "3. Write the passage following the system-prompt rules. Ground every factual claim and "
        "every quantity in what you actually read. Do not paraphrase from memory.\n"
        "4. Cite only papers you have web_fetched in this turn. If a fetched paper turns out not "
        "to support the claim, drop the claim or find a different paper - do not cite it anyway.\n"
        "5. Prefer a shorter paragraph with verified citations over a longer one with fabricated "
        "ones. If you cannot ground the topic in any fetched paper, write the paragraph with no "
        "references and an explicit 'References: none verified' line."
    )


def extract_text(content) -> str:
    return "".join(b.text for b in content if getattr(b, "type", None) == "text")


def call_with_pause_turn(client, **kwargs):
    response = client.messages.create(**kwargs)
    while response.stop_reason == "pause_turn":
        kwargs["messages"] = [
            *kwargs["messages"],
            {"role": "assistant", "content": response.content},
        ]
        response = client.messages.create(**kwargs)
    return response


def generate_grounded_body(client, model: str, system_prompt: str, stub: str, category: str) -> str:
    """Call Claude with web_search + web_fetch tools and a verifier-feedback retry loop."""
    tools = [
        {"type": "web_search_20260209", "name": "web_search"},
        {"type": "web_fetch_20260209", "name": "web_fetch"},
    ]
    messages = [{"role": "user", "content": build_user_message(stub, category)}]
    create_kwargs = dict(
        model=model,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=system_prompt,
        tools=tools,
        messages=messages,
    )

    response = call_with_pause_turn(client, **create_kwargs)
    body = extract_text(response.content)

    for attempt in range(MAX_VERIFY_RETRIES):
        refs = parse_references(body)
        if not refs:
            return body
        results = verify_references(refs)
        if all_passed(results):
            return body
        feedback = (
            "Some of the references in the passage do not resolve. Re-search and rewrite using "
            "ONLY URLs you have actually web_fetched and verified to load successfully in this "
            "turn. If you cannot find verifiable replacements, omit references entirely and add "
            "'References: none verified'. Failed:\n" + failure_summary(results)
        )
        messages = [
            *create_kwargs["messages"],
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": feedback},
        ]
        create_kwargs["messages"] = messages
        response = call_with_pause_turn(client, **create_kwargs)
        body = extract_text(response.content)

    final_refs = parse_references(body)
    if final_refs and not all_passed(verify_references(final_refs)):
        raise RuntimeError(
            "Reference verification still failing after retry; aborting send rather than "
            "emailing unverified citations."
        )
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full grounded generation and print the rendered email; skip SMTP and skip state write.",
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
    model = os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL

    try:
        body = generate_grounded_body(client, model, system_prompt, stub, category)
    except RuntimeError as e:
        print(f"ABORT: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"Subject: {subject}")
        print(f"Category: {category}")
        print(f"Stub: {stub}")
        print(f"Model: {model}")
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
    print(f"Email sent to {recipient_address} (model={model}, category={category}, stub={stub!r})")


if __name__ == "__main__":
    main()
