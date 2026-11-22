export interface HealthDiagnostic {
  status: string;
  app: string;
  version: string;
  environment: string;
  timestamp: string;
  database: {
    status: string;
    path: string;
    journal_mode: string;
  };
  hardware: {
    os: string;
    cpu_model: string;
    logical_cores: number;
    gpu_type: string;
    cuda_available: boolean;
    disk_free_gb: number;
    recommended_device: string;
    recommended_compute_type: string;
    recommended_whisper_model: string;
    ffmpeg_encoder: string;
    storage_constrained: boolean;
  };
  media_tools: {
    ffmpeg_available: boolean;
    ffprobe_available: boolean;
    details: {
      ffmpeg: string;
      ffprobe: string;
    };
  };
}

export interface Project {
  id: string;
  title: string;
  source_file_path: string;
  duration_seconds: number;
  width: number;
  height: number;
  fps: number;
  video_codec: string;
  audio_codec: string;
  has_audio: boolean;
  file_size_bytes: number;
  container_format: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface Word {
  index: number;
  start: number;
  end: number;
  word: string;
  probability: number;
}

export interface Segment {
  id: number;
  start: number;
  end: number;
  text: string;
  words: Word[];
}

export interface Transcript {
  project_id: string;
  language: string;
  language_probability: number;
  duration: number;
  text: string;
  segments: Segment[];
  words: Word[];
}

export interface TranscriptionStatus {
  project_id: string;
  status: string;
  phase?: string;
  model: string;
  model_cached?: boolean;
  progress_percent: number;
  model_load_duration?: number | null;
  inference_duration?: number | null;
  total_duration?: number | null;
  language: string | null;
  language_probability: number | null;
  word_count: number;
  error: string | null;
  is_running: boolean;
}

export interface Clip {
  id: string;
  project_id: string;
  start_word_index: number;
  end_word_index: number;
  start_time: number;
  end_time: number;
  title: string;
  hook: string;
  description: string;
  rationale: string;
  category: string;
  engagement_score: number;
  validation_status: string;
  validation_reason: string;
  selected: boolean;
  status: string;
  created_at?: string | null;
}

export interface HighlightDiscoveryStatus {
  project_id: string;
  status: string;
  progress_percent: number;
  candidate_count: number;
  mode: string;
  error: string | null;
  is_running: boolean;
}



