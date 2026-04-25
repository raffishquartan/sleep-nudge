"""Tests for scripts.reference_verifier."""

from __future__ import annotations

from scripts.reference_verifier import (
    FetchResult,
    Reference,
    VerificationResult,
    all_passed,
    failure_summary,
    parse_references,
    verify_references,
)


SAMPLE_BODY = """\
Slow-wave sleep ramps growth-hormone pulsatility (Van Cauter et al. 1992, 30% larger amplitude vs sleep deprivation).
This is mediated by ...

Plain language: get to bed early so growth hormone can do its job overnight.

References
Van Cauter, E., et al. (1992). Modulation of GH pulsatility by sleep. JCI. https://www.jci.org/articles/view/12345
Steiger, A. (2003). Sleep and the hypothalamo-pituitary-adrenocortical system. Sleep Med Rev. https://pmc.ncbi.nlm.nih.gov/articles/PMC9999/

---
"""


def test_parse_references_finds_urls_in_references_section():
    refs = parse_references(SAMPLE_BODY)
    assert len(refs) == 2
    assert refs[0].url == "https://www.jci.org/articles/view/12345"
    assert refs[1].url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC9999/"


def test_parse_references_returns_empty_when_no_references_section():
    body = "A paragraph without any references section.\n"
    assert parse_references(body) == []


def test_parse_references_strips_trailing_punctuation():
    body = "References\nSomeone (2020). Title. Journal. https://example.com/paper.\n"
    refs = parse_references(body)
    assert refs[0].url == "https://example.com/paper"


def test_parse_references_skips_horizontal_rule_and_blanks():
    body = "References\n\nA. Author (2020). T. J. https://example.com/a\n---\n"
    refs = parse_references(body)
    assert len(refs) == 1


def test_verify_references_marks_200_as_ok():
    refs = [Reference("Smith (2020). T. J. https://example.com/a", "https://example.com/a")]
    fake_fetch = lambda url: FetchResult(status=200)
    results = verify_references(refs, fetch=fake_fetch)
    assert results[0].ok
    assert all_passed(results)


def test_verify_references_marks_404_as_failed():
    refs = [Reference("Smith (2020). T. J. https://example.com/missing", "https://example.com/missing")]
    fake_fetch = lambda url: FetchResult(status=404, error="Not Found")
    results = verify_references(refs, fetch=fake_fetch)
    assert not results[0].ok
    assert not all_passed(results)


def test_failure_summary_lists_only_failed_refs():
    results = [
        VerificationResult(Reference("a", "https://a/"), ok=True, detail="HTTP 200"),
        VerificationResult(Reference("b", "https://b/"), ok=False, detail="HTTP 404"),
    ]
    summary = failure_summary(results)
    assert "https://b/" in summary
    assert "https://a/" not in summary


def test_failure_summary_empty_when_all_passed():
    results = [VerificationResult(Reference("a", "https://a/"), ok=True, detail="HTTP 200")]
    assert failure_summary(results) == ""


def test_http_head_refuses_file_scheme():
    from scripts.reference_verifier import http_head

    result = http_head("file:///etc/passwd")
    assert result.status == 0
    assert "non-http(s)" in (result.error or "")
