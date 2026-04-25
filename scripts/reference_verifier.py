"""Post-generation verifier: parse references from a body and check each URL resolves."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import requests


URL_PATTERN = re.compile(r"https?://\S+")
ALLOWED_SCHEMES = frozenset({"http", "https"})
USER_AGENT = "sleep-nudge-verifier/1.0"


@dataclass
class Reference:
    line: str
    url: str


@dataclass
class FetchResult:
    status: int
    error: str | None = None


@dataclass
class VerificationResult:
    reference: Reference
    ok: bool
    detail: str


def parse_references(body: str) -> list[Reference]:
    lines = body.splitlines()
    in_refs = False
    out: list[Reference] = []
    for raw in lines:
        line = raw.strip()
        if not in_refs:
            if line.lower().startswith("references"):
                in_refs = True
            continue
        if line.startswith("---") or not line:
            continue
        m = URL_PATTERN.search(line)
        if m:
            out.append(Reference(line=line, url=m.group(0).rstrip(".,;)")))
    return out


def http_head(url: str, timeout: float = 10.0) -> FetchResult:
    scheme = urlparse(url).scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        return FetchResult(status=0, error=f"refusing non-http(s) scheme: {scheme!r}")
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code in (403, 405):
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
            resp.close()
        return FetchResult(status=resp.status_code)
    except requests.RequestException as e:
        return FetchResult(status=0, error=str(e))


def verify_references(
    refs: list[Reference],
    fetch: Callable[[str], FetchResult] = http_head,
) -> list[VerificationResult]:
    results = []
    for ref in refs:
        r = fetch(ref.url)
        if r.status == 200:
            results.append(VerificationResult(ref, ok=True, detail=f"HTTP {r.status}"))
        else:
            results.append(
                VerificationResult(
                    ref,
                    ok=False,
                    detail=f"HTTP {r.status}{f' ({r.error})' if r.error else ''}",
                )
            )
    return results


def all_passed(results: list[VerificationResult]) -> bool:
    return all(r.ok for r in results)


def failure_summary(results: list[VerificationResult]) -> str:
    failed = [r for r in results if not r.ok]
    if not failed:
        return ""
    return "\n".join(f"- {r.reference.url}: {r.detail}" for r in failed)
