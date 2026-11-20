"""Speech-to-Text Transcription Subsystem.

Wraps faster-whisper with CTranslate2 INT8 execution on CPU, Silero VAD filtering,
word-level timestamp indexing, language detection, and persistent disk artifacts.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from clipforge.core.config import settings
from clipforge.core.logging import logger
from clipforge.db.session import get_db_connection
from clipforge.media.ffmpeg import ffmpeg_engine


class TranscriptionError(Exception):
    """Base exception for transcription operations."""
    pass


class AudioFileNotFoundError(TranscriptionError):
    """Raised when source audio file is missing or unreadable."""
    pass


class ModelLoadError(TranscriptionError):
    """Raised when Whisper model cannot be loaded."""
    pass


class TranscriptionEngine:
    """Production wrapper around faster-whisper WhisperModel."""

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        cpu_threads: Optional[int] = None,
        download_root: Optional[Path] = None,
    ):
        self.model_size = model_size or settings.model_size
        self.device = device or settings.device
        self.compute_type = compute_type or settings.compute_type
        self.cpu_threads = cpu_threads or settings.cpu_threads
        self.download_root = download_root or settings.whisper_model_dir

        self._model = None
        self._lock = threading.Lock()

    def get_model(self):
        """Lazy thread-safe initialization of WhisperModel."""
        if self._model is not None:
            return self._model
        return self._load_model()

    def _load_model(self):
        """Internal loader for WhisperModel."""
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel

                    logger.info(
                        f"Loading WhisperModel: model={self.model_size}, device={self.device}, "
                        f"compute_type={self.compute_type}, threads={self.cpu_threads}, cache={self.download_root}"
                    )
                    self.download_root.mkdir(parents=True, exist_ok=True)
                    self._model = WhisperModel(
                        model_size_or_path=self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                        cpu_threads=self.cpu_threads,
                        download_root=str(self.download_root.resolve()),
                    )
                    logger.info(f"WhisperModel '{self.model_size}' loaded successfully.")
                except Exception as e:
                    logger.error(f"Failed to load WhisperModel: {e}")
                    raise ModelLoadError(f"Failed to load Whisper model '{self.model_size}': {e}")
        return self._model

    def transcribe_file(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        vad_filter: bool = True,
    ) -> Dict[str, Any]:
        """Transcribe a standardized 16kHz WAV file and extract word-level timestamps."""
        if not audio_path.exists() or not audio_path.is_file():
            raise AudioFileNotFoundError(f"Audio file not found: {audio_path}")

        if audio_path.stat().st_size == 0:
            raise AudioFileNotFoundError("Audio file is empty (0 bytes).")

        model = self.get_model()

        try:
            logger.info(f"Starting faster-whisper transcription for {audio_path.name}...")
            segments_generator, info = model.transcribe(
                str(audio_path.resolve()),
                vad_filter=vad_filter,
                word_timestamps=True,
                language=language,
            )

            all_segments: List[Dict[str, Any]] = []
            all_words: List[Dict[str, Any]] = []
            global_word_idx = 0

            for seg in segments_generator:
                segment_words: List[Dict[str, Any]] = []

                if seg.words:
                    for w in seg.words:
                        cleaned_word = w.word.strip()
                        if not cleaned_word:
                            continue

                        word_dict = {
                            "index": global_word_idx,
                            "word": cleaned_word,
                            "start": round(float(w.start), 2),
                            "end": round(float(w.end), 2),
                            "probability": round(float(w.probability), 3) if w.probability is not None else 0.0,
                            "segment_id": seg.id,
                        }
                        segment_words.append(word_dict)
                        all_words.append(word_dict)
                        global_word_idx += 1

                all_segments.append(
                    {
                        "id": seg.id,
                        "start": round(float(seg.start), 2),
                        "end": round(float(seg.end), 2),
                        "text": seg.text.strip(),
                        "words": segment_words,
                    }
                )

            raw_text = " ".join(s["text"] for s in all_segments).strip()
            detected_lang = info.language if info and hasattr(info, "language") else "en"
            lang_prob = round(float(info.language_probability), 3) if info and hasattr(info, "language_probability") else 0.0
            duration = round(float(info.duration), 2) if info and hasattr(info, "duration") else 0.0

            logger.info(
                f"Transcription complete: words={len(all_words)}, segments={len(all_segments)}, "
                f"lang={detected_lang} ({lang_prob*100:.1f}%)"
            )

            return {
                "model": self.model_size,
                "language": detected_lang,
                "language_probability": lang_prob,
                "duration": duration,
                "raw_text": raw_text,
                "word_count": len(all_words),
                "segments": all_segments,
                "words": all_words,
            }

        except Exception as e:
            logger.error(f"Transcription error during inference: {e}")
            raise TranscriptionError(f"Inference error during transcription: {e}")

    @staticmethod
    def write_transcript_atomically(target_path: Path, payload: Dict[str, Any]) -> None:
        """Write JSON payload atomically using a temporary file in the same directory.

        Writes to `target_path.with_suffix('.tmp')`, flushes and syncs to disk,
        then replaces `target_path` atomically. Cleans up temp file on failure.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            temp_path.replace(target_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def transcribe_project(
        self,
        project_id: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Orchestrate transcription for a project, ensuring audio exists and persisting records."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
            project_row = cursor.fetchone()
            if not project_row:
                raise ValueError(f"Project '{project_id}' not found.")

        if not bool(project_row["has_audio"]):
            raise ValueError(f"Project '{project_id}' has no audio stream to transcribe.")

        project_dir = settings.projects_dir / project_id
        audio_file = project_dir / "audio_16k.wav"

        # If 16kHz mono audio is not yet extracted, extract it now via FFmpeg
        if not audio_file.exists():
            source_video = Path(project_row["source_file_path"]).resolve()
            logger.info(f"Audio not yet extracted for project {project_id}. Running FFmpeg extraction first...")
            ffmpeg_engine.extract_audio(source_video, audio_file)

        # Execute transcription
        transcript_data = self.transcribe_file(audio_file, language=language)

        # Write immutable artifact transcript.json into projects/{project_id}/ atomically
        transcript_json_path = project_dir / "transcript.json"
        artifact_payload = {
            "project_id": project_id,
            "created_at": datetime.utcnow().isoformat(),
            **transcript_data,
        }
        self.write_transcript_atomically(transcript_json_path, artifact_payload)

        # Persist summary in SQLite transcripts table
        now_iso = datetime.utcnow().isoformat()
        transcript_id = f"tr_{project_id}"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transcripts (
                    id, project_id, raw_text, words_json_path, language,
                    language_probability, model_name, word_count, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    raw_text=excluded.raw_text,
                    words_json_path=excluded.words_json_path,
                    language=excluded.language,
                    language_probability=excluded.language_probability,
                    model_name=excluded.model_name,
                    word_count=excluded.word_count,
                    status=excluded.status,
                    created_at=excluded.created_at;
                """,
                (
                    transcript_id,
                    project_id,
                    transcript_data["raw_text"],
                    str(transcript_json_path.resolve()),
                    transcript_data["language"],
                    transcript_data["language_probability"],
                    transcript_data["model"],
                    transcript_data["word_count"],
                    "COMPLETED",
                    now_iso,
                ),
            )
            cursor.execute(
                "UPDATE projects SET status = 'TRANSCRIBED', updated_at = ? WHERE id = ?;",
                (now_iso, project_id),
            )
            conn.commit()

        logger.info(f"Persisted transcript for project {project_id} (word_count={transcript_data['word_count']})")
        return artifact_payload

    def transcribe_audio(
        self,
        audio_path: Path,
        project_id: Optional[str] = None,
        language: Optional[str] = None,
    ):
        """Transcribe audio file directly, optionally persisting artifact and returning TranscriptModel."""
        from clipforge.db.models import TranscriptModel, SegmentModel, WordModel

        if not audio_path.exists() or not audio_path.is_file():
            raise AudioFileNotFoundError(f"Audio file not found: {audio_path}")

        transcript_data = self.transcribe_file(audio_path, language=language)

        if project_id:
            project_dir = settings.get_project_dir(project_id)
            project_dir.mkdir(parents=True, exist_ok=True)
            transcript_json_path = project_dir / "transcript.json"

            artifact_payload = {
                "project_id": project_id,
                "created_at": datetime.utcnow().isoformat(),
                **transcript_data,
            }
            self.write_transcript_atomically(transcript_json_path, artifact_payload)

            now_iso = datetime.utcnow().isoformat()
            transcript_id = f"tr_{project_id}"

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO transcripts (
                        id, project_id, raw_text, words_json_path, language,
                        language_probability, model_name, word_count, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        raw_text=excluded.raw_text,
                        words_json_path=excluded.words_json_path,
                        language=excluded.language,
                        language_probability=excluded.language_probability,
                        model_name=excluded.model_name,
                        word_count=excluded.word_count,
                        status=excluded.status,
                        created_at=excluded.created_at;
                    """,
                    (
                        transcript_id,
                        project_id,
                        transcript_data["raw_text"],
                        str(transcript_json_path.resolve()),
                        transcript_data["language"],
                        transcript_data["language_probability"],
                        transcript_data["model"],
                        transcript_data["word_count"],
                        "COMPLETED",
                        now_iso,
                    ),
                )
                cursor.execute(
                    "UPDATE projects SET status = 'TRANSCRIBED', updated_at = ? WHERE id = ?;",
                    (now_iso, project_id),
                )
                conn.commit()

        # Build TranscriptModel
        segments = [
            SegmentModel(
                id=s["id"],
                start=s["start"],
                end=s["end"],
                text=s["text"],
                words=[
                    WordModel(
                        index=w["index"],
                        word=w["word"],
                        start=w["start"],
                        end=w["end"],
                        probability=w.get("probability", 0.0),
                    )
                    for w in s.get("words", [])
                ],
            )
            for s in transcript_data.get("segments", [])
        ]

        words = [
            WordModel(
                index=w["index"],
                word=w["word"],
                start=w["start"],
                end=w["end"],
                probability=w.get("probability", 0.0),
            )
            for w in transcript_data.get("words", [])
        ]

        return TranscriptModel(
            id=f"tr_{project_id}" if project_id else "tr_temp",
            project_id=project_id or "",
            language=transcript_data.get("language", "en"),
            language_probability=transcript_data.get("language_probability", 0.0),
            duration=transcript_data.get("duration", 0.0),
            text=transcript_data.get("raw_text", ""),
            segments=segments,
            words=words,
        )

    def get_transcript(self, project_id: str):
        """Retrieve full structured transcript model for a project."""
        from clipforge.db.models import TranscriptModel, SegmentModel, WordModel

        project_dir = settings.get_project_dir(project_id)
        transcript_json_path = project_dir / "transcript.json"

        if not transcript_json_path.exists():
            return None

        with open(transcript_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        segments = [
            SegmentModel(
                id=s["id"],
                start=s["start"],
                end=s["end"],
                text=s["text"],
                words=[
                    WordModel(
                        index=w["index"],
                        word=w["word"],
                        start=w["start"],
                        end=w["end"],
                        probability=w.get("probability", 0.0),
                    )
                    for w in s.get("words", [])
                ],
            )
            for s in data.get("segments", [])
        ]

        words = [
            WordModel(
                index=w["index"],
                word=w["word"],
                start=w["start"],
                end=w["end"],
                probability=w.get("probability", 0.0),
            )
            for w in data.get("words", [])
        ]

        return TranscriptModel(
            id=f"tr_{project_id}",
            project_id=project_id,
            language=data.get("language", "en"),
            language_probability=data.get("language_probability", 0.0),
            duration=data.get("duration", 0.0),
            text=data.get("raw_text", ""),
            segments=segments,
            words=words,
        )

    def get_transcription_status(self, project_id: str) -> Dict[str, Any]:
        """Query transcription status from database."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transcripts WHERE project_id = ?;", (project_id,))
            row = cursor.fetchone()

        if not row:
            return {
                "project_id": project_id,
                "status": "NOT_STARTED",
                "language": None,
                "language_probability": None,
                "word_count": 0,
                "is_running": False,
            }

        return {
            "project_id": project_id,
            "status": row["status"],
            "language": row["language"],
            "language_probability": row["language_probability"],
            "word_count": row["word_count"],
            "is_running": row["status"] in ("RUNNING", "IN_PROGRESS"),
        }


# Global singleton instance
transcription_engine = TranscriptionEngine()
