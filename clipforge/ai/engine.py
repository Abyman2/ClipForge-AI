"""AI Highlight Discovery and Validation Orchestration Engine.

Coordinates transcript chunking, LLM analysis (with offline heuristic fallback),
deterministic boundary validation, candidate merging, explainable ranking,
and atomic disk & database persistence.
"""

import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from clipforge.ai.adapter import (
    HighlightCandidate,
    HighlightDiscoveryResponse,
    HIGHLIGHT_SYSTEM_PROMPT,
    build_highlight_user_prompt,
    LLMAdapterInterface,
)
from clipforge.ai.chunking import chunk_transcript
from clipforge.ai.validator import validator, ValidationResult
from clipforge.core.config import settings
from clipforge.core.logging import logger
from clipforge.db.models import ClipModel, TranscriptModel, WordModel
from clipforge.db.session import get_db_connection


class HeuristicHighlightDiscoverer:
    """Offline heuristic analyzer for highlight candidate extraction.

    Used when no external LLM API key is configured, or during offline testing,
    guaranteeing reliable, deterministic clip discovery without cloud dependencies.
    """

    def __init__(self, target_min_duration: float = 18.0, target_max_duration: float = 65.0):
        self.target_min_duration = target_min_duration
        self.target_max_duration = target_max_duration
        self.terminal_punct = {".", "!", "?"}

    def discover_candidates(self, words: List[WordModel]) -> List[HighlightCandidate]:
        """Extract candidate clips using sentence clustering and speech cadence heuristics."""
        if not words:
            return []

        total_words = len(words)
        total_duration = words[-1].end - words[0].start

        # If the whole video is short (e.g. 15-90s), the entire transcript is a primary candidate
        candidates: List[HighlightCandidate] = []
        if total_duration <= self.target_max_duration and total_duration >= 10.0:
            first_sentence_words = []
            for w in words[:15]:
                first_sentence_words.append(w.word)
                if any(w.word.endswith(p) for p in self.terminal_punct):
                    break
            hook_text = " ".join(first_sentence_words) or "Key insight from this video"

            candidates.append(
                HighlightCandidate(
                    start_word_index=0,
                    end_word_index=total_words - 1,
                    title="Full Video Highlight",
                    hook=hook_text,
                    description=f"Self-contained segment capturing the complete message ({total_duration:.1f}s).",
                    rationale="[Offline Heuristic Discovery] Video duration is within target short-clip bounds.",
                    category="insight",
                    engagement_score=8.5,
                )
            )

        # Find sentence boundary indices
        sentence_boundaries: List[int] = [0]
        for i, w in enumerate(words):
            if any(w.word.endswith(p) for p in self.terminal_punct) and i < total_words - 1:
                sentence_boundaries.append(i + 1)
        if sentence_boundaries[-1] != total_words:
            sentence_boundaries.append(total_words)

        # Slide windows across sentence boundaries to form candidate segments
        for start_idx_pos in range(len(sentence_boundaries) - 1):
            w_start = sentence_boundaries[start_idx_pos]
            for end_idx_pos in range(start_idx_pos + 1, len(sentence_boundaries)):
                w_end = sentence_boundaries[end_idx_pos] - 1
                if w_end <= w_start:
                    continue

                duration = words[w_end].end - words[w_start].start
                if self.target_min_duration <= duration <= self.target_max_duration:
                    # Construct hook from first sentence
                    first_sent_end = sentence_boundaries[start_idx_pos + 1] - 1
                    hook_words = [w.word for w in words[w_start : min(first_sent_end + 1, w_start + 12)]]
                    hook = " ".join(hook_words)

                    # Determine category based on keywords
                    segment_text = " ".join(w.word.lower() for w in words[w_start : w_end + 1])
                    category = "insight"
                    if "?" in hook or "how" in segment_text or "why" in segment_text:
                        category = "tutorial"
                    elif "story" in segment_text or "remember" in segment_text or "happened" in segment_text:
                        category = "story"
                    elif "think" in segment_text or "believe" in segment_text or "never" in segment_text:
                        category = "opinion"

                    score = 7.5
                    # Duration sweet spot bonus
                    if 25.0 <= duration <= 50.0:
                        score += 0.8
                    if "?" in hook:
                        score += 0.5

                    title_words = [w.word.capitalize() for w in words[w_start : min(w_start + 5, w_end + 1)]]
                    title = " ".join(title_words).strip(".,?!")

                    candidates.append(
                        HighlightCandidate(
                            start_word_index=w_start,
                            end_word_index=w_end,
                            title=title,
                            hook=hook,
                            description=f"Engaging {category} moment ({duration:.1f}s) starting with strong hook.",
                            rationale="[Offline Heuristic Discovery] Natural sentence cluster with strong hook and balanced duration.",
                            category=category,
                            engagement_score=round(min(9.5, score), 1),
                        )
                    )

        return candidates


class HighlightDiscoveryEngine:
    """Production highlight discovery and boundary validation engine."""

    def __init__(self, adapter: Optional[LLMAdapterInterface] = None):
        self.adapter = adapter or LLMAdapterInterface()
        self.heuristic_discoverer = HeuristicHighlightDiscoverer()

    def discover_highlights_for_project(
        self,
        project_id: str,
        video_duration: Optional[float] = None,
    ) -> List[ClipModel]:
        """Execute the complete highlight discovery and boundary validation pipeline.

        Args:
            project_id: Unique project identifier.
            video_duration: Optional video duration in seconds for boundary safety.

        Returns:
            List of validated, ranked, and persisted ClipModel instances.
        """
        logger.info(f"[HighlightEngine] Starting highlight discovery for project {project_id}")

        # 1. Retrieve project transcript and metadata from DB / disk
        words, duration = self._load_transcript_words(project_id)
        if not words:
            logger.warning(f"[HighlightEngine] Project {project_id} has no transcript words.")
            return []

        effective_duration = video_duration or duration

        # 2. Extract highlight candidates (LLM or Heuristic Fallback)
        raw_candidates: List[HighlightCandidate] = []
        discovery_mode = "llm" if self.adapter.has_api_key else "heuristic_offline"

        if self.adapter.has_api_key:
            logger.info(
                f"[HighlightEngine] Using external LLM API ({self.adapter.model}, protocol={self.adapter.protocol})"
            )
            chunks = chunk_transcript(words, max_words_per_chunk=500, overlap_words=80)
            for chunk in chunks:
                try:
                    user_prompt = build_highlight_user_prompt(chunk.formatted_text)
                    resp_dict = self.adapter.call_llm(
                        system_prompt=HIGHLIGHT_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                    )
                    hl_resp = HighlightDiscoveryResponse.model_validate(resp_dict)
                    raw_candidates.extend(hl_resp.highlights)
                except Exception as e:
                    logger.error(f"[HighlightEngine] Error querying LLM for chunk {chunk.chunk_index}: {e}")
        else:
            logger.info(
                "[HighlightEngine] No LLM API key configured. Executing offline heuristic discovery."
            )
            raw_candidates = self.heuristic_discoverer.discover_candidates(words)

        logger.info(f"[HighlightEngine] Gathered {len(raw_candidates)} raw candidate(s) via {discovery_mode}")

        # 3. Deterministic 4-Rule Boundary Validation
        validated_candidates: List[Dict[str, Any]] = []
        for cand in raw_candidates:
            val_res: ValidationResult = validator.validate_candidate(
                start_word_index=cand.start_word_index,
                end_word_index=cand.end_word_index,
                words=words,
                video_duration=effective_duration,
            )

            if val_res.is_valid:
                validated_candidates.append(
                    {
                        "candidate": cand,
                        "validation": val_res,
                    }
                )
            else:
                logger.debug(
                    f"[HighlightEngine] Candidate [{cand.start_word_index}-{cand.end_word_index}] rejected: {val_res.validation_reason}"
                )

        # 4. Candidate Merging and Deduplication
        merged_candidates = self._merge_overlapping_candidates(validated_candidates, words)

        # 5. Explainable Candidate Ranking
        ranked_clips = self._rank_and_construct_clips(project_id, merged_candidates)
        logger.info(f"[HighlightEngine] Produced {len(ranked_clips)} ranked clip candidate(s).")

        # 6. Atomic Persistence (Disk & Database)
        self._persist_candidates_atomic(project_id, ranked_clips)

        return ranked_clips

    def _load_transcript_words(self, project_id: str) -> tuple[List[WordModel], float]:
        """Load word models and duration from project transcript disk artifact or DB."""
        project_work_dir = settings.data_dir / "projects" / project_id / "work"
        transcript_json_path = project_work_dir / "transcript.json"

        words: List[WordModel] = []
        duration: float = 0.0

        if transcript_json_path.exists():
            try:
                with open(transcript_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    duration = float(data.get("duration", 0.0))
                    raw_words = data.get("words", [])
                    for idx, w in enumerate(raw_words):
                        words.append(
                            WordModel(
                                index=w.get("index", idx),
                                word=w.get("word", "").strip(),
                                start=float(w.get("start", 0.0)),
                                end=float(w.get("end", 0.0)),
                                probability=float(w.get("probability", 1.0)),
                            )
                        )
                return words, duration
            except Exception as e:
                logger.error(f"[HighlightEngine] Failed to read {transcript_json_path}: {e}")

        # Fallback to database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT duration_seconds FROM projects WHERE id = ?;", (project_id,))
            p_row = cursor.fetchone()
            if p_row:
                duration = float(p_row["duration_seconds"])

        return words, duration

    def _merge_overlapping_candidates(
        self,
        validated_items: List[Dict[str, Any]],
        words: List[WordModel],
    ) -> List[Dict[str, Any]]:
        """Merge heavily overlapping or duplicate candidates."""
        if not validated_items:
            return []

        # Sort by start_time
        sorted_items = sorted(
            validated_items,
            key=lambda x: (x["validation"].start_time, -x["candidate"].engagement_score),
        )

        merged: List[Dict[str, Any]] = []

        for item in sorted_items:
            cand = item["candidate"]
            val = item["validation"]

            if not merged:
                merged.append(item)
                continue

            prev = merged[-1]
            prev_val = prev["validation"]
            prev_cand = prev["candidate"]

            # Calculate temporal Intersection over Union (IoU)
            intersection_start = max(val.start_time, prev_val.start_time)
            intersection_end = min(val.end_time, prev_val.end_time)
            intersection = max(0.0, intersection_end - intersection_start)

            union_start = min(val.start_time, prev_val.start_time)
            union_end = max(val.end_time, prev_val.end_time)
            union = union_end - union_start

            iou = (intersection / union) if union > 0 else 0.0

            # If overlap > 0.45 or start times are within 3 seconds, merge into higher-scoring candidate
            if iou > 0.45 or abs(val.start_time - prev_val.start_time) < 3.0:
                if cand.engagement_score > prev_cand.engagement_score:
                    # Replace with current item
                    merged[-1] = item
                # Else keep previous item
            else:
                merged.append(item)

        return merged

    def _rank_and_construct_clips(
        self,
        project_id: str,
        items: List[Dict[str, Any]],
    ) -> List[ClipModel]:
        """Score, rank, and format candidates into ClipModel objects."""
        clips: List[ClipModel] = []

        for item in items:
            cand: HighlightCandidate = item["candidate"]
            val: ValidationResult = item["validation"]

            # Compute explainable ranking score
            base_score = float(cand.engagement_score)
            duration = val.duration_seconds

            # 1. Retention sweet spot bonus (25s - 55s is optimal for vertical shorts)
            duration_bonus = 0.0
            if 25.0 <= duration <= 55.0:
                duration_bonus = 0.6
            elif 20.0 <= duration <= 70.0:
                duration_bonus = 0.3
            else:
                duration_bonus = -0.2

            # 2. Hook clarity bonus (short, punchy opening hooks)
            hook_words = cand.hook.split()
            hook_bonus = 0.3 if (3 <= len(hook_words) <= 12) else 0.0

            # 3. Validation status bonus
            validation_bonus = 0.2 if val.validation_status == "VALID" else 0.0

            final_score = round(min(10.0, max(1.0, base_score + duration_bonus + hook_bonus + validation_bonus)), 1)

            clip_id = f"clip_{uuid.uuid4().hex[:10]}"
            clips.append(
                ClipModel(
                    id=clip_id,
                    project_id=project_id,
                    start_word_index=val.start_word_index,
                    end_word_index=val.end_word_index,
                    start_time=val.start_time,
                    end_time=val.end_time,
                    title=cand.title or f"Highlight ({val.start_time:.1f}s - {val.end_time:.1f}s)",
                    hook=cand.hook,
                    description=cand.description,
                    rationale=cand.rationale,
                    category=cand.category,
                    engagement_score=final_score,
                    validation_status=val.validation_status,
                    validation_reason=val.validation_reason,
                    selected=False,
                    status="DISCOVERED",
                    created_at=datetime.utcnow(),
                )
            )

        # Sort descending by engagement_score
        clips.sort(key=lambda c: c.engagement_score, reverse=True)
        return clips

    def _persist_candidates_atomic(self, project_id: str, clips: List[ClipModel]) -> None:
        """Atomically write candidates to disk artifact and store in SQLite."""
        project_work_dir = settings.data_dir / "projects" / project_id / "work"
        project_work_dir.mkdir(parents=True, exist_ok=True)
        candidates_file = project_work_dir / "candidates.json"

        # 1. Atomic disk persistence
        payload = {
            "project_id": project_id,
            "generated_at": datetime.utcnow().isoformat(),
            "candidate_count": len(clips),
            "clips": [c.model_dump(mode="json") for c in clips],
        }

        temp_fd, temp_path = tempfile.mkstemp(
            prefix="candidates_",
            suffix=".tmp",
            dir=str(project_work_dir),
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            # Atomic rename / replace
            os.replace(temp_path, candidates_file)
            logger.info(f"[HighlightEngine] Atomically saved candidates artifact to {candidates_file}")
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"[HighlightEngine] Failed atomic write of {candidates_file}: {e}")
            raise

        # 2. SQLite Database persistence
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Clear previous clips for this project
            cursor.execute("DELETE FROM clips WHERE project_id = ?;", (project_id,))

            for c in clips:
                cursor.execute(
                    """
                    INSERT INTO clips (
                        id, project_id, start_word_index, end_word_index,
                        start_time, end_time, title, hook, description,
                        rationale, category, engagement_score, validation_status,
                        validation_reason, selected, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        c.id,
                        c.project_id,
                        c.start_word_index,
                        c.end_word_index,
                        c.start_time,
                        c.end_time,
                        c.title,
                        c.hook,
                        c.description,
                        c.rationale,
                        c.category,
                        c.engagement_score,
                        c.validation_status,
                        c.validation_reason,
                        1 if c.selected else 0,
                        c.status,
                    ),
                )

            # Update project status to HIGHLIGHTS_READY
            cursor.execute(
                "UPDATE projects SET status = 'HIGHLIGHTS_READY', updated_at = ? WHERE id = ?;",
                (datetime.utcnow().isoformat(), project_id),
            )
            conn.commit()
            logger.info(f"[HighlightEngine] Persisted {len(clips)} clips into database for project {project_id}")


highlight_engine = HighlightDiscoveryEngine()

