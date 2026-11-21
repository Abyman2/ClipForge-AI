"""Unit tests for transcript chunking and word index preservation."""

import pytest
from clipforge.ai.chunking import chunk_transcript, TranscriptChunk
from clipforge.db.models import WordModel


def make_words(count: int, sentence_len: int = 10) -> list[WordModel]:
    """Helper to generate sequential synthetic WordModel items with punctuation."""
    words = []
    for i in range(count):
        is_sentence_end = (i + 1) % sentence_len == 0
        word_text = f"word{i}." if is_sentence_end else f"word{i}"
        words.append(
            WordModel(
                index=i,
                word=word_text,
                start=round(i * 0.4, 2),
                end=round((i * 0.4) + 0.35, 2),
                probability=0.98,
            )
        )
    return words


def test_chunk_empty_words():
    """Empty list should return zero chunks."""
    assert chunk_transcript([]) == []


def test_chunk_short_transcript_single_chunk():
    """Short transcript under max_words_per_chunk should produce exactly one chunk."""
    words = make_words(45)
    chunks = chunk_transcript(words, max_words_per_chunk=100)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].start_word_index == 0
    assert chunks[0].end_word_index == 44
    assert len(chunks[0].words) == 45
    # Verify index formatting
    assert "[0] word0" in chunks[0].formatted_text
    assert "[44] word44" in chunks[0].formatted_text


def test_chunk_long_transcript_overlapping_chunks():
    """Long transcripts should produce multiple overlapping chunks preserving word indices."""
    words = make_words(250, sentence_len=15)
    chunks = chunk_transcript(words, max_words_per_chunk=100, overlap_words=25)
    assert len(chunks) >= 3

    # Check that indices strictly advance
    for i in range(len(chunks) - 1):
        c1 = chunks[i]
        c2 = chunks[i + 1]
        assert c2.start_word_index > c1.start_word_index
        assert c2.start_word_index < c1.end_word_index  # Overlap exists
        assert c2.chunk_index == c1.chunk_index + 1

    # Final chunk should reach the end
    assert chunks[-1].end_word_index == 249


def test_chunk_respects_sentence_boundary():
    """Chunks should prefer splitting at sentence boundaries (terminal punctuation)."""
    words = make_words(120, sentence_len=20)
    chunks = chunk_transcript(words, max_words_per_chunk=60, overlap_words=15)
    assert len(chunks) >= 2

    # Verify the first chunk ends with terminal punctuation
    first_chunk_last_word = chunks[0].words[-1].word
    assert any(first_chunk_last_word.endswith(p) for p in [".", "!", "?"])
