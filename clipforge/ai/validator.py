"""Deterministic 4-Rule Word-Index Boundary Validator.

Validates highlight candidate boundaries using Whisper word timings,
enforcing index bounds, sentence snapping, physical duration constraints,
and internal dead-air checks.
"""

from typing import List, Optional
from pydantic import BaseModel
from clipforge.db.models import WordModel


class ValidationResult(BaseModel):
    """Result of running boundary validation on a candidate clip."""
    is_valid: bool
    validation_status: str  # "VALID", "ADJUSTED", "REJECTED"
    validation_reason: str
    start_word_index: int
    end_word_index: int
    start_time: float
    end_time: float
    duration_seconds: float


class WordIndexValidator:
    """Enforces deterministic boundary validation on LLM highlight candidates."""

    def __init__(
        self,
        min_duration_seconds: float = 15.0,
        max_duration_seconds: float = 90.0,
        max_silence_gap_seconds: float = 3.0,
        silence_boundary_threshold: float = 0.75,
        max_snap_window_words: int = 10,
    ):
        self.min_duration = min_duration_seconds
        self.max_duration = max_duration_seconds
        self.max_silence_gap = max_silence_gap_seconds
        self.silence_boundary_threshold = silence_boundary_threshold
        self.max_snap_window = max_snap_window_words
        self.terminal_punctuation = {".", "!", "?"}

    def validate_candidate(
        self,
        start_word_index: int,
        end_word_index: int,
        words: List[WordModel],
        video_duration: Optional[float] = None,
    ) -> ValidationResult:
        """Execute the 4-rule deterministic validation pipeline.

        Args:
            start_word_index: Raw proposed start word index.
            end_word_index: Raw proposed end word index.
            words: Complete ordered list of WordModel items.
            video_duration: Total video duration in seconds (optional).

        Returns:
            ValidationResult with status ("VALID", "ADJUSTED", "REJECTED"),
            reasons, and verified physical timestamps.
        """
        total_words = len(words)

        # -------------------------------------------------------------
        # Rule 1: Index Bounds Integrity
        # -------------------------------------------------------------
        if total_words == 0:
            return ValidationResult(
                is_valid=False,
                validation_status="REJECTED",
                validation_reason="Transcript contains zero words.",
                start_word_index=start_word_index,
                end_word_index=end_word_index,
                start_time=0.0,
                end_time=0.0,
                duration_seconds=0.0,
            )

        if not (0 <= start_word_index < end_word_index < total_words):
            return ValidationResult(
                is_valid=False,
                validation_status="REJECTED",
                validation_reason=(
                    f"Index bounds violation: start={start_word_index}, "
                    f"end={end_word_index}, total_words={total_words}."
                ),
                start_word_index=max(0, min(start_word_index, total_words - 1)),
                end_word_index=max(0, min(end_word_index, total_words - 1)),
                start_time=0.0,
                end_time=0.0,
                duration_seconds=0.0,
            )

        snapped_start = start_word_index
        snapped_end = end_word_index
        was_adjusted = False
        adjustment_notes = []

        # -------------------------------------------------------------
        # Rule 2: Sentence Boundary Snapping
        # -------------------------------------------------------------
        # Backward scan from start_word_index to snap to sentence start
        # A sentence start is:
        # a) Word 0
        # b) Preceding word ends with terminal punctuation
        # c) Gap between preceding word and current word > silence_boundary_threshold
        # d) Current word starts with capital letter and preceding word is punctuated
        best_start = snapped_start
        min_start_bound = max(0, snapped_start - self.max_snap_window)

        for i in range(snapped_start, min_start_bound - 1, -1):
            if i == 0:
                best_start = 0
                break
            prev_word = words[i - 1].word.strip()
            silence_before = words[i].start - words[i - 1].end

            if any(prev_word.endswith(p) for p in self.terminal_punctuation) or silence_before >= self.silence_boundary_threshold:
                best_start = i
                break

        if best_start != snapped_start:
            snapped_start = best_start
            was_adjusted = True
            adjustment_notes.append(f"Snapped start from index {start_word_index} to {best_start}")

        # Forward scan from end_word_index to snap to sentence end
        # A sentence end is:
        # a) Current word ends with terminal punctuation
        # b) Silence following current word >= silence_boundary_threshold
        # c) Last word of transcript
        best_end = snapped_end
        max_end_bound = min(total_words - 1, snapped_end + self.max_snap_window)

        for i in range(snapped_end, max_end_bound + 1):
            curr_word = words[i].word.strip()
            if i == total_words - 1:
                best_end = i
                break
            silence_after = words[i + 1].start - words[i].end
            if any(curr_word.endswith(p) for p in self.terminal_punctuation) or silence_after >= self.silence_boundary_threshold:
                best_end = i
                break

        if best_end != snapped_end:
            snapped_end = best_end
            was_adjusted = True
            adjustment_notes.append(f"Snapped end from index {end_word_index} to {best_end}")

        # Re-verify start < end after snapping
        if snapped_start >= snapped_end:
            snapped_start = start_word_index
            snapped_end = end_word_index

        # -------------------------------------------------------------
        # Derive Physical Timestamps Strictly from Word Models
        # -------------------------------------------------------------
        start_time = round(words[snapped_start].start, 3)
        end_time = round(words[snapped_end].end, 3)
        duration = round(end_time - start_time, 3)

        # -------------------------------------------------------------
        # Rule 3: Physical Duration Constraints (15s <= ΔT <= 90s)
        # -------------------------------------------------------------
        # Allow a small 0.5s grace on the lower bound for short high-impact hooks if needed,
        # but enforce strict threshold
        if duration < self.min_duration:
            # Try to extend end forward up to min_duration if words exist
            extended_end = snapped_end
            while extended_end < total_words - 1 and (words[extended_end].end - words[snapped_start].start) < self.min_duration:
                extended_end += 1

            new_duration = words[extended_end].end - words[snapped_start].start
            if self.min_duration <= new_duration <= self.max_duration:
                snapped_end = extended_end
                end_time = round(words[snapped_end].end, 3)
                duration = round(end_time - start_time, 3)
                was_adjusted = True
                adjustment_notes.append(f"Extended duration to {duration}s to meet {self.min_duration}s minimum")
            else:
                return ValidationResult(
                    is_valid=False,
                    validation_status="REJECTED",
                    validation_reason=f"Candidate duration ({duration:.2f}s) is shorter than minimum {self.min_duration:.1f}s.",
                    start_word_index=snapped_start,
                    end_word_index=snapped_end,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                )

        if duration > self.max_duration:
            # Try to contract end backward to nearest sentence boundary within max_duration
            contracted_end = snapped_end
            found_contract = False
            for i in range(snapped_end - 1, snapped_start, -1):
                cur_dur = words[i].end - words[snapped_start].start
                if cur_dur <= self.max_duration:
                    curr_word = words[i].word.strip()
                    if any(curr_word.endswith(p) for p in self.terminal_punctuation) or cur_dur <= self.max_duration - 5.0:
                        contracted_end = i
                        found_contract = True
                        break

            if found_contract and (words[contracted_end].end - words[snapped_start].start) >= self.min_duration:
                snapped_end = contracted_end
                end_time = round(words[snapped_end].end, 3)
                duration = round(end_time - start_time, 3)
                was_adjusted = True
                adjustment_notes.append(f"Trimmed duration to {duration}s to stay within {self.max_duration}s maximum")
            else:
                return ValidationResult(
                    is_valid=False,
                    validation_status="REJECTED",
                    validation_reason=f"Candidate duration ({duration:.2f}s) exceeds maximum {self.max_duration:.1f}s.",
                    start_word_index=snapped_start,
                    end_word_index=snapped_end,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                )

        # -------------------------------------------------------------
        # Rule 4: Internal Silence & Dead-Air Check
        # -------------------------------------------------------------
        for i in range(snapped_start, snapped_end):
            gap = words[i + 1].start - words[i].end
            if gap > self.max_silence_gap:
                return ValidationResult(
                    is_valid=False,
                    validation_status="REJECTED",
                    validation_reason=f"Internal dead-air gap ({gap:.2f}s) between words {i} and {i+1} exceeds {self.max_silence_gap:.1f}s limit.",
                    start_word_index=snapped_start,
                    end_word_index=snapped_end,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                )

        # -------------------------------------------------------------
        # Video Duration Boundary Check
        # -------------------------------------------------------------
        if video_duration is not None and video_duration > 0:
            if end_time > (video_duration + 0.5):
                return ValidationResult(
                    is_valid=False,
                    validation_status="REJECTED",
                    validation_reason=f"Candidate end time ({end_time:.2f}s) exceeds video duration ({video_duration:.2f}s).",
                    start_word_index=snapped_start,
                    end_word_index=snapped_end,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                )

        status_label = "ADJUSTED" if was_adjusted else "VALID"
        reason_label = "; ".join(adjustment_notes) if adjustment_notes else "Passed all 4 boundary validation rules."

        return ValidationResult(
            is_valid=True,
            validation_status=status_label,
            validation_reason=reason_label,
            start_word_index=snapped_start,
            end_word_index=snapped_end,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
        )


validator = WordIndexValidator()

