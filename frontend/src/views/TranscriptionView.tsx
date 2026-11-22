import React, { useState, useEffect } from 'react';
import {
  FileText,
  RefreshCw,
  Languages,
  AlertCircle,
  Clock,
  ArrowRight,
  FolderOpen,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { Project, Transcript, TranscriptionStatus } from '../types';

interface TranscriptionViewProps {
  projects: Project[];
  selectedProject: Project | null;
  onSelectProject: (proj: Project) => void;
  onProjectsChange: () => void;
  onNavigateTab?: (tab: string) => void;
}

export const TranscriptionView: React.FC<TranscriptionViewProps> = ({
  projects,
  selectedProject,
  onSelectProject,
  onProjectsChange,
  onNavigateTab,
}) => {
  const [transcribing, setTranscribing] = useState<boolean>(false);
  const [transcriptionStatus, setTranscriptionStatus] = useState<TranscriptionStatus | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [selectedWordIndex, setSelectedWordIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

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
            onProjectsChange();
          } else if (status.status === 'FAILED') {
            clearInterval(interval);
            setTranscribing(false);
            setError(status.error || 'Transcription failed');
            onProjectsChange();
          }
        }
      } catch {
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

  useEffect(() => {
    if (selectedProject) {
      setSelectedWordIndex(null);
      setError(null);
      if (selectedProject.status === 'TRANSCRIBED' || selectedProject.status === 'HIGHLIGHTS_READY') {
        fetchTranscript(selectedProject.id);
      } else {
        setTranscript(null);
      }
    } else {
      setTranscript(null);
    }
  }, [selectedProject?.id]);

  const formatDuration = (seconds: number) => {
    if (!seconds || seconds <= 0) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const isAudioReady =
    selectedProject &&
    (selectedProject.status === 'AUDIO_READY' ||
      selectedProject.status === 'TRANSCRIBED' ||
      selectedProject.status === 'HIGHLIGHTS_READY' ||
      selectedProject.status === 'FAILED');

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner & Project Selector Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/80 border border-slate-800">
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400">
              <FileText className="w-4 h-4" />
            </div>
            <h2 className="text-lg font-bold text-white">Speech-to-Text Transcription (Stage 2.3)</h2>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-400/10 border border-amber-400/20 text-amber-400 font-semibold">
              faster-whisper • CPU int8
            </span>
          </div>
          <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
            Local CTranslate2-accelerated speech-to-text with Silero VAD silence filtering, word-level timestamps, and language detection.
          </p>
        </div>

        {/* Project Selector Dropdown */}
        {projects.length > 0 && (
          <div className="flex items-center space-x-2 shrink-0">
            <span className="text-xs text-slate-400 font-medium">Project:</span>
            <select
              value={selectedProject?.id || ''}
              onChange={(e) => {
                const found = projects.find((p) => p.id === e.target.value);
                if (found) onSelectProject(found);
              }}
              className="bg-slate-850 text-slate-200 border border-slate-700 rounded-xl px-3 py-2 text-xs font-semibold focus:outline-none focus:border-amber-400 transition-colors"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} ({p.status})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Main Content */}
      {selectedProject ? (
        <div className="space-y-6">
          {/* Project Status Bar */}
          <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-center space-x-4">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  selectedProject.has_audio
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                }`}
              >
                {selectedProject.has_audio ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">{selectedProject.title}</h3>
                <div className="flex items-center space-x-3 text-xs text-slate-400 mt-0.5">
                  <span className="font-mono">Duration: {formatDuration(selectedProject.duration_seconds)}</span>
                  <span>•</span>
                  <span>Audio: {selectedProject.audio_codec?.toUpperCase() || 'None'}</span>
                  <span>•</span>
                  <span
                    className={`font-mono text-[10px] px-2 py-0.5 rounded font-semibold ${
                      selectedProject.status === 'TRANSCRIBED' || selectedProject.status === 'HIGHLIGHTS_READY'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : selectedProject.status === 'AUDIO_READY'
                        ? 'bg-amber-400/10 text-amber-400 border border-amber-400/20'
                        : selectedProject.status === 'FAILED'
                        ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    {selectedProject.status}
                  </span>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center space-x-3">
              {isAudioReady ? (
                <button
                  onClick={() => handleTranscribe(selectedProject.id)}
                  disabled={transcribing}
                  className={`px-4 py-2.5 rounded-xl text-xs font-semibold flex items-center space-x-2 transition-all shadow-md ${
                    transcribing
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30 cursor-not-allowed'
                      : 'bg-amber-400 hover:bg-amber-300 text-slate-950 shadow-amber-400/10'
                  }`}
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${transcribing ? 'animate-spin' : ''}`} />
                  <span>
                    {transcribing
                      ? 'Transcribing Speech...'
                      : selectedProject.status === 'TRANSCRIBED' || selectedProject.status === 'HIGHLIGHTS_READY'
                      ? 'Re-transcribe Audio'
                      : selectedProject.status === 'FAILED'
                      ? 'Retry Transcription'
                      : 'Transcribe Audio'}
                  </span>
                </button>
              ) : (
                <div className="flex items-center space-x-2 text-xs text-amber-400 bg-amber-400/10 px-3 py-2 rounded-xl border border-amber-400/20">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Audio not extracted yet.</span>
                  {onNavigateTab && (
                    <button
                      onClick={() => onNavigateTab('import')}
                      className="underline font-semibold ml-1 hover:text-amber-300"
                    >
                      Extract Audio in Video Ingest &rarr;
                    </button>
                  )}
                </div>
              )}

              {/* Next Step Shortcut */}
              {(selectedProject.status === 'TRANSCRIBED' || selectedProject.status === 'HIGHLIGHTS_READY') &&
                onNavigateTab && (
                  <button
                    onClick={() => onNavigateTab('highlights')}
                    className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition-colors"
                  >
                    <span>Proceed to AI Highlights</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="flex items-center space-x-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Transcribing Progress Banner */}
          {transcribing && (
            <div className="p-4 rounded-xl bg-amber-400/5 border border-amber-400/20 flex items-center space-x-3 text-xs text-amber-300">
              <RefreshCw className="w-4 h-4 animate-spin text-amber-400 shrink-0" />
              <span>
                {transcriptionStatus?.is_running
                  ? 'Transcribing speech with 4 CPU threads (Whisper tiny int8). Generating word-level timestamps...'
                  : 'Initializing faster-whisper CTranslate2 model...'}
              </span>
            </div>
          )}

          {/* Word-Level Transcript Viewer */}
          {transcript ? (
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-5">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
                <div className="flex items-center space-x-3">
                  <div className="flex items-center space-x-1.5 text-xs text-slate-300 font-mono">
                    <Languages className="w-4 h-4 text-amber-400" />
                    <span>Detected Language:</span>
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
                  <div className="text-xs font-mono text-amber-400 bg-amber-400/10 px-3 py-1.5 rounded-lg border border-amber-400/20">
                    Word #{selectedWordIndex}: &ldquo;{transcript.words[selectedWordIndex].word.trim()}&rdquo; [
                    {transcript.words[selectedWordIndex].start.toFixed(2)}s –{' '}
                    {transcript.words[selectedWordIndex].end.toFixed(2)}s] (
                    {(transcript.words[selectedWordIndex].probability * 100).toFixed(0)}% conf)
                  </div>
                )}
              </div>

              {/* Segments and Interactive Word Tokens */}
              <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
                {transcript.segments.map((seg) => (
                  <div
                    key={seg.id}
                    className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/60 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                      <div className="flex items-center space-x-1.5">
                        <Clock className="w-3 h-3 text-slate-600" />
                        <span>
                          [{formatDuration(seg.start)} – {formatDuration(seg.end)}]
                        </span>
                      </div>
                      <span>Segment #{seg.id}</span>
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
          ) : (
            !transcribing && (
              <div className="p-12 text-center rounded-2xl border border-dashed border-slate-800 space-y-3 bg-slate-900/20">
                <FileText className="w-10 h-10 text-slate-600 mx-auto" />
                <div className="text-sm font-medium text-slate-300">No transcript available for this project</div>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  {selectedProject.status === 'AUDIO_READY'
                    ? 'Click "Transcribe Audio" above to run faster-whisper speech-to-text.'
                    : 'Extract audio in Video Ingest first before running speech-to-text.'}
                </p>
              </div>
            )
          )}
        </div>
      ) : (
        /* Empty State: No Project Selected */
        <div className="p-12 text-center rounded-2xl border border-dashed border-slate-800 space-y-4 bg-slate-900/20">
          <FolderOpen className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="text-base font-semibold text-slate-200">No Video Project Selected</div>
          <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
            Please select an existing project from the dropdown above or import new video footage in the Video Ingest workspace.
          </p>
          {onNavigateTab && (
            <button
              onClick={() => onNavigateTab('import')}
              className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 text-xs font-semibold transition-colors"
            >
              <span>Go to Video Ingest</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      )}
    </div>
  );
};
