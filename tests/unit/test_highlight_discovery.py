"""Unit tests for AI highlight discovery, candidate merging, and ranking."""

import json
from pathlib import Path
import pytest

from clipforge.ai.adapter import (
    clean_json_markdown,
    HighlightCandidate,
    HighlightDiscoveryResponse,
    LLMAdapterInterface,
)
from clipforge.ai.engine import (
    HeuristicHighlightDiscoverer,
    HighlightDiscoveryEngine,
)
from clipforge.ai.validator import ValidationResult
from clipforge.db.models import WordModel


def test_clean_json_markdown():
    """Markdown code blocks should be stripped cleanly."""
    raw = "```json\n{\"highlights\": []}\n```"
    assert clean_json_markdown(raw) == '{"highlights": []}'

    raw2 = "```\n{\"key\": \"val\"}\n```"
    assert clean_json_markdown(raw2) == '{"key": "val"}'

    raw_clean = '{"highlights": []}'
    assert clean_json_markdown(raw_clean) == '{"highlights": []}'


def test_heuristic_highlight_discoverer():
    """Heuristic discoverer extracts candidates with complete sentences and hooks."""
    words = []
    # Create 80 words (approx 35 seconds of speech) with multiple sentences
    sentences = [
        "Welcome to ClipForge AI.",
        "Today we are going to show you how to automate viral short clipping completely on your laptop.",
        "Why is local processing so powerful?",
        "Because your video footage never leaves your workstation, protecting your privacy.",
        "And that is why you should start using it today.",
    ]
    w_idx = 0
    t = 0.0
    for s in sentences:
        for w in s.split():
            words.append(
                WordModel(
                    index=w_idx,
                    word=w,
                    start=round(t, 2),
                    end=round(t + 0.35, 2),
                    probability=0.99,
                )
            )
            w_idx += 1
            t += 0.45

    discoverer = HeuristicHighlightDiscoverer(target_min_duration=10.0, target_max_duration=40.0)
    candidates = discoverer.discover_candidates(words)

    assert len(candidates) >= 1
    for c in candidates:
        assert c.start_word_index < c.end_word_index
        assert c.title != ""
        assert c.hook != ""
        assert "[Offline Heuristic Discovery]" in c.rationale
        assert 1.0 <= c.engagement_score <= 10.0


def test_candidate_merging_deduplication():
    """Heavily overlapping candidates should merge into the higher-scoring clip."""
    engine = HighlightDiscoveryEngine()
    words = [
        WordModel(index=i, word=f"w{i}", start=round(i * 0.4, 2), end=round(i * 0.4 + 0.35, 2), probability=1.0)
        for i in range(100)
    ]

    # Two heavily overlapping items: 10-50 (start=4.0, end=20.35) and 12-52 (start=4.8, end=21.15)
    item1 = {
        "candidate": HighlightCandidate(
            start_word_index=10,
            end_word_index=50,
            title="Clip 1",
            hook="Hook 1",
            engagement_score=7.5,
        ),
        "validation": ValidationResult(
            is_valid=True,
            validation_status="VALID",
            validation_reason="OK",
            start_word_index=10,
            end_word_index=50,
            start_time=4.0,
            end_time=20.35,
            duration_seconds=16.35,
        ),
    }

    item2 = {
        "candidate": HighlightCandidate(
            start_word_index=12,
            end_word_index=52,
            title="Clip 2 Higher Score",
            hook="Hook 2",
            engagement_score=9.0,
        ),
        "validation": ValidationResult(
            is_valid=True,
            validation_status="VALID",
            validation_reason="OK",
            start_word_index=12,
            end_word_index=52,
            start_time=4.8,
            end_time=21.15,
            duration_seconds=16.35,
        ),
    }

    merged = engine._merge_overlapping_candidates([item1, item2], words)
    assert len(merged) == 1
    # Higher score should win
    assert merged[0]["candidate"].title == "Clip 2 Higher Score"


def test_ranking_and_construction():
    """Ranking applies bonuses for duration sweet spot and punchy hooks."""
    engine = HighlightDiscoveryEngine()
    item_sweet_spot = {
        "candidate": HighlightCandidate(
            start_word_index=0,
            end_word_index=70,
            title="Ideal Duration Clip",
            hook="Why you must do this now",
            engagement_score=8.0,
        ),
        "validation": ValidationResult(
            is_valid=True,
            validation_status="VALID",
            validation_reason="Passed",
            start_word_index=0,
            end_word_index=70,
            start_time=0.0,
            end_time=35.0,
            duration_seconds=35.0,  # 35s is in sweet spot (25-55s)
        ),
    }

    item_long = {
        "candidate": HighlightCandidate(
            start_word_index=80,
            end_word_index=280,
            title="Long Clip",
            hook="A somewhat longer story that takes quite a bit of time to unfold here",
            engagement_score=8.0,
        ),
        "validation": ValidationResult(
            is_valid=True,
            validation_status="ADJUSTED",
            validation_reason="Snapped",
            start_word_index=80,
            end_word_index=280,
            start_time=40.0,
            end_time=125.0,
            duration_seconds=85.0,  # 85s outside sweet spot
        ),
    }

    clips = engine._rank_and_construct_clips("test_proj", [item_sweet_spot, item_long])
    assert len(clips) == 2
    # Sweet spot clip should rank first
    assert clips[0].title == "Ideal Duration Clip"
    assert clips[0].engagement_score > clips[1].engagement_score

