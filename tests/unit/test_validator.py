"""Unit tests for the 4-rule deterministic boundary validator."""

import pytest
from clipforge.ai.validator import WordIndexValidator
from clipforge.db.models import WordModel


def make_words_with_timestamps(
    count: int,
    word_duration: float = 0.4,
    gap: float = 0.1,
    sentence_len: int = 10,
) -> list[WordModel]:
    """Generate sequential synthetic words with exact timestamps and sentences."""
    words = []
    current_time = 0.0
    for i in range(count):
        is_sentence_end = (i + 1) % sentence_len == 0
        word_text = f"word{i}." if is_sentence_end else f"word{i}"
        start_t = round(current_time, 3)
        end_t = round(start_t + word_duration, 3)
        words.append(
            WordModel(
                index=i,
                word=word_text,
                start=start_t,
                end=end_t,
                probability=0.99,
            )
        )
        current_time = end_t + gap
    return words


def test_rule1_index_bounds_integrity():
    """Rule 1: Rejects out of bounds, inverted, or negative indices."""
    v = WordIndexValidator()
    words = make_words_with_timestamps(50)

    # Empty words
    res = v.validate_candidate(0, 10, [])
    assert not res.is_valid
    assert res.validation_status == "REJECTED"

    # Inverted indices
    res = v.validate_candidate(20, 10, words)
    assert not res.is_valid
    assert "Index bounds violation" in res.validation_reason

    # Equal indices
    res = v.validate_candidate(15, 15, words)
    assert not res.is_valid

    # Out of bounds
    res = v.validate_candidate(10, 60, words)
    assert not res.is_valid


def test_rule2_sentence_snapping():
    """Rule 2: Snaps boundaries to natural sentence endpoints."""
    v = WordIndexValidator(min_duration_seconds=5.0, max_duration_seconds=90.0)
    # Sentence ends every 10 words (e.g. index 9, 19, 29, 39, etc.)
    words = make_words_with_timestamps(60, sentence_len=10)

    # Start proposed at 12 (mid-sentence). Should snap back to 10 (first word of sentence)
    # End proposed at 43 (mid-sentence). Should snap forward to 49 (word49.)
    res = v.validate_candidate(12, 43, words)
    assert res.is_valid
    assert res.validation_status == "ADJUSTED"
    assert res.start_word_index == 10
    assert res.end_word_index == 49
    assert "Snapped start" in res.validation_reason
    assert "Snapped end" in res.validation_reason


def test_rule3_duration_constraints():
    """Rule 3: Enforces minimum and maximum duration constraints."""
    # 5 words * 0.5s = 2.5s duration (much less than 15s)
    v = WordIndexValidator(min_duration_seconds=15.0, max_duration_seconds=60.0)
    words = make_words_with_timestamps(100, word_duration=0.4, gap=0.1)

    # Very short range at end of transcript where expansion cannot reach 15s
    res = v.validate_candidate(95, 98, words)
    assert not res.is_valid
    assert "shorter than minimum" in res.validation_reason

    # Very long range (e.g. 80 words = 40s duration, valid)
    res_valid = v.validate_candidate(10, 60, words)
    assert res_valid.is_valid
    assert res_valid.duration_seconds >= 15.0
    assert res_valid.duration_seconds <= 60.0


def test_rule4_dead_air_silence_detection():
    """Rule 4: Flags or rejects candidates with internal silence gap > 3.0 seconds."""
    v = WordIndexValidator(min_duration_seconds=10.0, max_duration_seconds=90.0, max_silence_gap_seconds=3.0)
    words = make_words_with_timestamps(60)

    # Inject a 4.5-second dead-air gap between word 24 and word 25
    words[25].start = words[24].end + 4.5
    for j in range(26, len(words)):
        words[j].start += 4.5
        words[j].end += 4.5

    res = v.validate_candidate(10, 40, words)
    assert not res.is_valid
    assert res.validation_status == "REJECTED"
    assert "dead-air gap" in res.validation_reason


def test_video_duration_boundary_check():
    """Rejects candidates extending past actual video duration."""
    v = WordIndexValidator(min_duration_seconds=10.0, max_duration_seconds=90.0)
    words = make_words_with_timestamps(50)  # total duration ~25s

    # Video duration is only 15 seconds, but candidate ends at ~22s
    res = v.validate_candidate(0, 44, words, video_duration=15.0)
    assert not res.is_valid
    assert "exceeds video duration" in res.validation_reason

