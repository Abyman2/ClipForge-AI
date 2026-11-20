import React, { useState, useEffect, useRef } from 'react';
import {
  UploadCloud,
  FileVideo,
  CheckCircle2,
  AlertCircle,
  Play,
  Volume2,
  VolumeX,
  Trash2,
  Clock,
  Layers,
  HardDrive,
  RefreshCw,
  Sparkles,
  FileText,
  Languages,
} from 'lucide-react';
import { Project, Transcript, TranscriptionStatus } from '../types';

interface VideoIngestViewProps {
  onProjectSelected?: (project: Project) => void;
}

export const VideoIngestView: React.FC<VideoIngestViewProps> = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [extractingAudio, setExtractingAudio] = useState<boolean>(false);
  const [audioResult, setAudioResult] = useState<string | null>(null);
  const [transcribing, setTranscribing] = useState<boolean>(false);
  const [transcriptionStatus, setTranscriptionStatus] = useState<TranscriptionStatus | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [selectedWordIndex, setSelectedWordIndex] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchTranscript = async (projectId: string) => {
    try {
      const res = await fetch(`/api/projects/${projectId}/transcript`);
      if (res.ok) {
        const data: Transcript = await res.json();
        setTranscript(data);
      } else {
        setTranscript(null);
      }
    } catch {
      setTranscript(null);
    }
  };

  const pollTranscription = (projectId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/projects/${projectId}/transcription-status`);
        if (res.ok) {
          const status: TranscriptionStatus = await res.json();
          setTranscriptionStatus(status);
          if (status.status === 'TRANSCRIBED') {
            clearInterval(interval);
            setTranscribing(false);
            fetchTranscript(projectId);
            fetchProjects();
          } else if (status.status === 'FAILED') {
            clearInterval(interval);
            setTranscribing(false);
            setError(status.error || 'Transcription failed');
            fetchProjects();
          }
        }
      } catch (e) {
        clearInterval(interval);
        setTranscribing(false);
      }
    }, 1500);
  };

  const handleTranscribe = async (projectId: string) => {
    try {
      setTranscribing(true);
      setError(null);
      setTranscript(null);
      setTranscriptionStatus(null);
      const res = await fetch(`/api/projects/${projectId}/transcribe`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to start transcription');
      }
      pollTranscription(projectId);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Transcription failed';
      setError(message);
      setTranscribing(false);
    }
  };

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/projects');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Project[] = await res.json();
      setProjects(data);
      if (data.length > 0 && !selectedProject) {
        setSelectedProject(data[0]);
        if (data[0].status === 'TRANSCRIBED') {
          fetchTranscript(data[0].id);
        }
      }
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load projects';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleUploadFile = (file: File) => {
    const validExtensions = ['.mp4', '.mov', '.mkv', '.webm'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!validExtensions.includes(ext)) {
      setError(`Unsupported video format "${ext}". Allowed: ${validExtensions.join(', ')}`);
      return;
    }

    setError(null);
    setAudioResult(null);
    setUploading(true);
    setUploadProgress(0);
    setUploadStatus('Uploading video stream...');

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/projects/upload');

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        setUploadProgress(percent);
        if (percent === 100) {
          setUploadStatus('Inspecting media container and extracting metadata...');
        }
      }
    };

    xhr.onload = () => {
      setUploading(false);
      if (xhr.status === 201) {
        try {
          const newProject: Project = JSON.parse(xhr.responseText);
          setProjects((prev) => [newProject, ...prev]);
          setSelectedProject(newProject);
          setUploadStatus('Video successfully ingested!');
        } catch {
          fetchProjects();
        }
      } else {
        try {
          const errData = JSON.parse(xhr.responseText);
          setError(errData.detail || 'Upload failed');
        } catch {
          setError(`Upload failed with HTTP ${xhr.status}`);
        }
      }
    };

    xhr.onerror = () => {
      setUploading(false);
      setError('Network error during video upload.');
    };

    xhr.send(formData);
  };

  const handleDeleteProject = async (id: string) => {
    if (!confirm('Are you sure you want to delete this project and its source video?')) return;
    try {
      const res = await fetch(`/api/projects/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setProjects((prev) => prev.filter((p) => p.id !== id));
      if (selectedProject?.id === id) {
        setSelectedProject(projects.find((p) => p.id !== id) || null);
      }
      setAudioResult(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete project';
      setError(message);
    }
  };

  const handleExtractAudio = async (projectId: string) => {
    try {
      setExtractingAudio(true);
      setAudioResult(null);
      setError(null);
      const res = await fetch(`/api/projects/${projectId}/extract-audio`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Audio extraction failed');
      }
      setAudioResult(`Extracted 16kHz mono WAV: ${data.audio_file_path}`);
      // Refresh current project
      const projRes = await fetch(`/api/projects/${projectId}`);
      if (projRes.ok) {
        const updated = await projRes.json();
        setSelectedProject(updated);
        setProjects((prev) => prev.map((p) => (p.id === projectId ? updated : p)));
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Audio extraction failed';
      setError(message);
    } finally {
      setExtractingAudio(false);
    }
  };

  const formatDuration = (seconds: number) => {
    if (!seconds || seconds <= 0) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return '0 MB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-full bg-amber-400/10 border border-amber-400/20 text-amber-400 text-xs font-medium mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Stage 2.2 — Local Video Ingestion & FFprobe Engine</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Video Ingest & Media Inspector</h1>
          <p className="text-sm text-slate-400">
            Upload local footage (.mp4, .mov, .mkv, .webm). Media streams are validated and inspected locally.
          </p>
        </div>

        <button
          onClick={fetchProjects}
          disabled={loading}
          className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-300 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start space-x-3 text-rose-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Ingestion Error: </span>
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-xs text-rose-400 hover:text-rose-200 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Audio Extraction Success Banner */}
      {audioResult && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-start space-x-3 text-emerald-300 text-sm">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-400 mt-0.5" />
          <div className="flex-1 font-mono text-xs">{audioResult}</div>
          <button
            onClick={() => setAudioResult(null)}
            className="text-xs text-emerald-400 hover:text-emerald-200 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Drag & Drop Upload Zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload video file (MP4, MOV, MKV, WebM up to 2 GB)"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!uploading) fileInputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleUploadFile(e.dataTransfer.files[0]);
          }
        }}
        onClick={() => !uploading && fileInputRef.current?.click()}
        className={`relative overflow-hidden rounded-2xl border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-amber-400 bg-amber-400/5'
            : 'border-slate-800 hover:border-slate-700 bg-slate-900/40 hover:bg-slate-900/60'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mov,.mkv,.webm"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleUploadFile(e.target.files[0]);
            }
          }}
        />

        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400 shadow-lg shadow-amber-400/5">
            <UploadCloud className="w-7 h-7" />
          </div>

          <div>
            <p className="text-base font-semibold text-slate-200">
              Drag & drop long-form video here, or <span className="text-amber-400 underline">browse files</span>
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Supports MP4, MOV, MKV, WebM up to 2 GB. Chunk-streamed directly to local SSD.
            </p>
          </div>

          {/* Upload Progress Bar */}
          {uploading && (
            <div className="w-full max-w-md space-y-2 mt-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between text-xs text-slate-400">
                <span>{uploadStatus}</span>
                <span className="font-semibold text-amber-400">{uploadProgress}%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 to-amber-300 transition-all duration-150"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content: Player + Metadata Inspector + Ingested List */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Player & Active Project Inspection */}
        <div className="lg:col-span-2 space-y-6">
          {selectedProject ? (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-6 space-y-6">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
                <div>
                  <h2 className="text-lg font-bold text-slate-100">{selectedProject.title}</h2>
                  <p className="text-xs text-slate-500 font-mono mt-0.5 truncate max-w-md">
                    {selectedProject.source_file_path}
                  </p>
                </div>

                <div className="flex items-center space-x-2">
                  <span
                    className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                      selectedProject.status === 'AUDIO_READY'
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                        : selectedProject.status === 'INGESTED'
                        ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                        : 'bg-slate-800 border-slate-700 text-slate-400'
                    }`}
                  >
                    {selectedProject.status}
                  </span>

                  <button
                    onClick={() => handleDeleteProject(selectedProject.id)}
                    className="p-2 rounded-lg bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-slate-700/60 transition-colors"
                    title="Delete Project"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Native HTML5 Video Stream Player */}
              <div className="rounded-xl overflow-hidden bg-black border border-slate-800 aspect-video flex items-center justify-center relative">
                <video
                  controls
                  className="w-full h-full object-contain"
                  src={`/api/projects/${selectedProject.id}/stream`}
                  preload="metadata"
                >
                  Your browser does not support the video tag.
                </video>
              </div>

              {/* Container Metadata Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-slate-850/60 border border-slate-800/80 space-y-1">
                  <div className="flex items-center space-x-1.5 text-slate-400 text-xs">
                    <Clock className="w-3.5 h-3.5 text-amber-400" />
                    <span>Duration</span>
                  </div>
                  <div className="text-sm font-semibold text-slate-100 font-mono">
                    {formatDuration(selectedProject.duration_seconds)}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-850/60 border border-slate-800/80 space-y-1">
                  <div className="flex items-center space-x-1.5 text-slate-400 text-xs">
                    <Layers className="w-3.5 h-3.5 text-amber-400" />
                    <span>Resolution</span>
                  </div>
                  <div className="text-sm font-semibold text-slate-100 font-mono">
                    {selectedProject.width > 0
                      ? `${selectedProject.width} × ${selectedProject.height}`
                      : 'Pending probe'}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-850/60 border border-slate-800/80 space-y-1">
                  <div className="flex items-center space-x-1.5 text-slate-400 text-xs">
                    <FileVideo className="w-3.5 h-3.5 text-amber-400" />
                    <span>Video Codec</span>
                  </div>
                  <div className="text-sm font-semibold text-slate-100 font-mono uppercase">
                    {selectedProject.video_codec || 'N/A'} {selectedProject.fps > 0 ? `(${selectedProject.fps} fps)` : ''}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-850/60 border border-slate-800/80 space-y-1">
                  <div className="flex items-center space-x-1.5 text-slate-400 text-xs">
                    <HardDrive className="w-3.5 h-3.5 text-amber-400" />
                    <span>File Size</span>
                  </div>
                  <div className="text-sm font-semibold text-slate-100 font-mono">
                    {formatFileSize(selectedProject.file_size_bytes)}
                  </div>
                </div>
              </div>

              {/* Audio Track & Extraction Control */}
              <div className="p-4 rounded-xl bg-slate-850/80 border border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                      selectedProject.has_audio
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    }`}
                  >
                    {selectedProject.has_audio ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-200">
                      {selectedProject.has_audio ? `Audio Track: ${selectedProject.audio_codec.toUpperCase()}` : 'No Audio Stream Detected'}
                    </div>
                    <div className="text-xs text-slate-400">
                      Standardized target: 16kHz 16-bit Mono PCM WAV for Whisper
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleExtractAudio(selectedProject.id)}
                  disabled={!selectedProject.has_audio || extractingAudio}
                  className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center space-x-2 transition-colors ${
                    !selectedProject.has_audio
                      ? 'bg-slate-800 text-slate-600 cursor-not-allowed'
                      : 'bg-amber-400 hover:bg-amber-300 text-slate-950 shadow-md shadow-amber-400/10'
                  }`}
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${extractingAudio ? 'animate-spin' : ''}`} />
                  <span>{extractingAudio ? 'Extracting Audio...' : 'Extract Audio (16kHz WAV)'}</span>
                </button>
              </div>

              {/* Speech-to-Text Transcription Control */}
              <div className="p-4 rounded-xl bg-slate-850/80 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-9 h-9 rounded-lg bg-amber-400/10 text-amber-400 border border-amber-400/20 flex items-center justify-center">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-slate-200">Speech-to-Text Transcription</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-amber-400 font-mono">
                          tiny • CPU int8
                        </span>
                      </div>
                      <div className="text-xs text-slate-400">
                        Local faster-whisper CTranslate2 with word-level timestamps
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleTranscribe(selectedProject.id)}
                    disabled={
                      transcribing ||
                      (selectedProject.status !== 'AUDIO_READY' &&
                        selectedProject.status !== 'TRANSCRIBED' &&
                        selectedProject.status !== 'FAILED')
                    }
                    className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center space-x-2 transition-colors ${
                      transcribing ||
                      (selectedProject.status !== 'AUDIO_READY' &&
                        selectedProject.status !== 'TRANSCRIBED' &&
                        selectedProject.status !== 'FAILED')
                        ? 'bg-slate-800 text-slate-600 cursor-not-allowed'
                        : 'bg-amber-400 hover:bg-amber-300 text-slate-950 shadow-md shadow-amber-400/10'
                    }`}
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${transcribing ? 'animate-spin' : ''}`} />
                    <span>
                      {transcribing
                        ? 'Transcribing Speech...'
                        : selectedProject.status === 'TRANSCRIBED'
                        ? 'Re-transcribe Audio'
                        : selectedProject.status === 'FAILED'
                        ? 'Retry Transcription'
                        : 'Transcribe Audio'}
                    </span>
                  </button>
                </div>

                {transcribing && (
                  <div className="p-3 rounded-lg bg-amber-400/5 border border-amber-400/20 flex items-center space-x-3 text-xs text-amber-300">
                    <RefreshCw className="w-4 h-4 animate-spin text-amber-400" />
                    <span>
                      {transcriptionStatus?.is_running
                        ? 'Processing speech using 4 CPU threads. Generating word timestamps...'
                        : 'Initializing faster-whisper CTranslate2 model (tiny int8)...'}
                    </span>
                  </div>
                )}
              </div>

              {/* Word-Level Transcript Viewer */}
              {transcript && (
                <div className="p-5 rounded-xl bg-slate-850/80 border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                    <div className="flex items-center space-x-3">
                      <div className="flex items-center space-x-1.5 text-xs text-slate-300 font-mono">
                        <Languages className="w-4 h-4 text-amber-400" />
                        <span>Language:</span>
                        <span className="font-bold uppercase text-amber-400">
                          {transcript.language} ({(transcript.language_probability * 100).toFixed(0)}%)
                        </span>
                      </div>
                      <span className="text-slate-600">•</span>
                      <div className="text-xs text-slate-300 font-mono">
                        Words: <span className="font-bold text-slate-100">{transcript.words.length}</span>
                      </div>
                      <span className="text-slate-600">•</span>
                      <div className="text-xs text-slate-300 font-mono">
                        Segments: <span className="font-bold text-slate-100">{transcript.segments.length}</span>
                      </div>
                    </div>

                    {selectedWordIndex !== null && transcript.words[selectedWordIndex] && (
                      <div className="text-xs font-mono text-amber-400 bg-amber-400/10 px-2.5 py-1 rounded border border-amber-400/20">
                        Word #{selectedWordIndex}: "{transcript.words[selectedWordIndex].word.trim()}" [
                        {transcript.words[selectedWordIndex].start.toFixed(2)}s –{' '}
                        {transcript.words[selectedWordIndex].end.toFixed(2)}s] (
                        {(transcript.words[selectedWordIndex].probability * 100).toFixed(0)}% conf)
                      </div>
                    )}
                  </div>

                  {/* Segments and Words display */}
                  <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                    {transcript.segments.map((seg) => (
                      <div
                        key={seg.id}
                        className="p-3 rounded-lg bg-slate-900/60 border border-slate-800/60 space-y-1.5 text-xs"
                      >
                        <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                          <span>
                            [{formatDuration(seg.start)} – {formatDuration(seg.end)}]
                          </span>
                          <span>Seg #{seg.id}</span>
                        </div>

                        <div className="flex flex-wrap gap-1 leading-relaxed">
                          {seg.words.map((w) => {
                            const isSelected = selectedWordIndex === w.index;
                            return (
                              <button
                                key={w.index}
                                onClick={() => setSelectedWordIndex(isSelected ? null : w.index)}
                                title={`#${w.index} [${w.start.toFixed(2)}s - ${w.end.toFixed(2)}s] (${(
                                  w.probability * 100
                                ).toFixed(0)}%)`}
                                className={`px-1.5 py-0.5 rounded text-xs transition-colors font-sans ${
                                  isSelected
                                    ? 'bg-amber-400 text-slate-950 font-bold shadow-sm shadow-amber-400/20'
                                    : 'hover:bg-slate-800 text-slate-300 hover:text-white'
                                }`}
                              >
                                {w.word}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/30 p-12 text-center text-slate-500">
              <FileVideo className="w-12 h-12 mx-auto mb-3 opacity-30 text-slate-400" />
              <p className="text-sm">No video selected. Upload a file above or select an existing project.</p>
            </div>
          )}
        </div>

        {/* Right Column: Ingested Projects History */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Ingested Projects ({projects.length})
            </h3>
          </div>

          <div className="space-y-3">
            {projects.length === 0 ? (
              <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/20 text-center text-xs text-slate-500">
                No videos imported yet.
              </div>
            ) : (
              projects.map((proj) => {
                const isSelected = selectedProject?.id === proj.id;
                return (
                  <div
                    key={proj.id}
                    role="button"
                    tabIndex={0}
                    aria-pressed={isSelected}
                    aria-label={`Select project ${proj.title}`}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedProject(proj);
                        setAudioResult(null);
                        setSelectedWordIndex(null);
                        if (proj.status === 'TRANSCRIBED') {
                          fetchTranscript(proj.id);
                        } else {
                          setTranscript(null);
                        }
                      }
                    }}
                    onClick={() => {
                      setSelectedProject(proj);
                      setAudioResult(null);
                      setSelectedWordIndex(null);
                      if (proj.status === 'TRANSCRIBED') {
                        fetchTranscript(proj.id);
                      } else {
                        setTranscript(null);
                      }
                    }}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-amber-400/50 bg-amber-400/5'
                        : 'border-slate-800 bg-slate-900/40 hover:bg-slate-800/60 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-2.5">
                        <div className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center text-amber-400">
                          <Play className="w-3.5 h-3.5 fill-current" />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold text-slate-200 line-clamp-1">{proj.title}</h4>
                          <span className="text-[11px] text-slate-500 font-mono">
                            {formatDuration(proj.duration_seconds)} • {formatFileSize(proj.file_size_bytes)}
                          </span>
                        </div>
                      </div>

                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                          proj.status === 'AUDIO_READY'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : proj.status === 'FAILED'
                            ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                            : 'bg-amber-400/10 text-amber-400 border border-amber-400/20'
                        }`}
                      >
                        {proj.status}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

