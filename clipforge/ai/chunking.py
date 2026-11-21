"""Transcript Chunking and Index Preservation Module.

Divides word-level transcripts into overlapping chunks for LLM processing
while preserving original word indices and respecting sentence boundaries.
"""

from typing import List
from pydantic import BaseModel
from clipforge.db.models import WordModel


class TranscriptChunk(BaseModel):
    """A slice of a transcript prepared for LLM highlight discovery."""
    chunk_index: int
    start_word_index: int
    end_word_index: int
    formatted_text: str
    words: List[WordModel] = []


def chunk_transcript(
    words: List[WordModel],
    max_words_per_chunk: int = 500,
    overlap_words: int = 100,
) -> List[TranscriptChunk]:
    """Divide a list of timestamped words into overlapping chunks.

    Args:
        words: Full list of WordModel items from transcription.
        max_words_per_chunk: Target maximum number of words per chunk.
        overlap_words: Number of words to overlap between consecutive chunks.

    Returns:
        List of TranscriptChunk objects with original word indices preserved.
    """
    if not words:
        return []

    total_words = len(words)

    # If the transcript is small enough, return as a single chunk
    if total_words <= max_words_per_chunk:
        chunk_text = " ".join(f"[{w.index}] {w.word}" for w in words)
        return [
            TranscriptChunk(
                chunk_index=0,
                start_word_index=words[0].index,
                end_word_index=words[-1].index,
                formatted_text=chunk_text,
                words=words,
            )
        ]

    chunks: List[TranscriptChunk] = []
    chunk_idx = 0
    start_pos = 0

    terminal_punct = {".", "?", "!"}

    while start_pos < total_words:
        target_end = min(start_pos + max_words_per_chunk, total_words)

        # If not at the very end of the transcript, look for a sentence boundary near target_end
        if target_end < total_words:
            # Search within a window of [-30, +15] words around target_end for terminal punctuation
            search_start = max(start_pos + 100, target_end - 30)
            search_end = min(total_words - 1, target_end + 15)
            best_boundary = target_end

            for i in range(search_end, search_start - 1, -1):
                word_clean = words[i].word.strip()
                if any(word_clean.endswith(p) for p in terminal_punct):
                    best_boundary = i + 1
                    break

            target_end = best_boundary

        chunk_words = words[start_pos:target_end]
        if not chunk_words:
            break

        chunk_text = " ".join(f"[{w.index}] {w.word}" for w in chunk_words)
        chunks.append(
            TranscriptChunk(
                chunk_index=chunk_idx,
                start_word_index=chunk_words[0].index,
                end_word_index=chunk_words[-1].index,
                formatted_text=chunk_text,
                words=chunk_words,
            )
        )
        chunk_idx += 1

        # Advance start_pos with overlap
        if target_end >= total_words:
            break

        # Move forward, maintaining overlap
        next_start = max(start_pos + 1, target_end - overlap_words)
        start_pos = next_start

    return chunks

