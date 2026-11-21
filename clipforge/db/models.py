"""Database data models and Pydantic schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProjectModel(BaseModel):
    """Pydantic representation of a Project."""
    id: str
    title: str
    source_file_path: str
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_codec: str = ""
    has_audio: bool = True
    file_size_bytes: int = 0
    container_format: str = ""
    status: str = "CREATED"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WordModel(BaseModel):
    """Pydantic representation of an individual word with timing and probability."""
    index: int
    word: str
    start: float
    end: float
    probability: float = 0.0


class SegmentModel(BaseModel):
    """Pydantic representation of a speech segment."""
    id: int
    start: float
    end: float
    text: str
    words: list[WordModel] = []


class TranscriptModel(BaseModel):
    """Pydantic representation of a Project Transcript."""
    id: str
    project_id: str
    language: str = "en"
    language_probability: float = 0.0
    model_name: str = "tiny"
    raw_text: str = ""
    words_json_path: str = ""
    word_count: int = 0
    segments: list[SegmentModel] = []
    words: list[WordModel] = []
    status: str = "COMPLETED"
    created_at: Optional[datetime] = None


class JobModel(BaseModel):
    """Pydantic representation of an asynchronous Job."""
    id: str
    project_id: str
    stage: str
    status: str = "PENDING"
    progress_percent: int = 0
    log_output: str = ""
    error_message: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ClipModel(BaseModel):
    """Pydantic representation of a Candidate Clip."""
    id: str
    project_id: str
    start_word_index: int
    end_word_index: int
    start_time: float
    end_time: float
    title: str
    hook: str = ""
    description: str = ""
    rationale: str = ""
    category: str = "general"
    engagement_score: float = 0.0
    validation_status: str = "VALID"
    validation_reason: str = ""
    selected: bool = False
    status: str = "DISCOVERED"
    created_at: Optional[datetime] = None

