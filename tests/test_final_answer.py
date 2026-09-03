"""Tests for the final-answer extractor."""

from deep_research.final_answer import extract_final_answer


def test_extract_direct_answer_section():
    report = """# How X works

*Generated: 2026-01-01 | Score: 80/100*

## 1. 直接回答

**X works by doing Y.** It is fast and reliable.

## 2. 关键证据

- Evidence A
"""
    ans = extract_final_answer(report)
    assert "X works by doing Y" in ans
    assert "Evidence A" not in ans


def test_extract_executive_summary_fallback():
    report = """# Title

*Generated: 2026-01-01*

## 执行摘要

This is the **short answer**.

## Other
"""
    ans = extract_final_answer(report)
    assert "short answer" in ans
    assert "Other" not in ans


def test_extract_first_paragraph_fallback():
    report = """# Title

First useful sentence here.

## Later
"""
    ans = extract_final_answer(report)
    assert ans.startswith("First useful sentence here.")


def test_extract_empty():
    assert extract_final_answer("") == ""


def test_extract_truncates():
    report = "# T\n\n## 1. 直接回答\n\n" + ("word " * 500)
    ans = extract_final_answer(report, max_chars=50)
    assert len(ans) <= 50
