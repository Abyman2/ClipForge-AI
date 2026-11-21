import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  AlertCircle,
  Clock,
  Star,
  Check,
  RefreshCw,
  Flame,
  Lightbulb,
  BookOpen,
  HelpCircle,
  Quote,
} from 'lucide-react';
import { Clip, HighlightDiscoveryStatus } from '../types';

interface HighlightCandidatesViewProps {
  projectId: string;
  projectStatus: string;
  onStatusChange?: () => void;
}

export const HighlightCandidatesView: React.FC<HighlightCandidatesViewProps> = ({
  projectId,
  projectStatus,
  onStatusChange,
}) => {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [discovering, setDiscovering] = useState<boolean>(false);
  const [statusInfo, setStatusInfo] = useState<HighlightDiscoveryStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const fetchHighlights = async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/projects/${projectId}/highlights`);
      if (res.ok) {
        const data: Clip[] = await res.json();
        setClips(data);
      } else {
        setClips([]);
      }
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch highlights';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/projects/${projectId}/highlights/status`);
      if (res.ok) {
        const data: HighlightDiscoveryStatus = await res.json();
        setStatusInfo(data);
        if (data.status === 'IN_PROGRESS') {
          setDiscovering(true);
        } else if (data.status === 'COMPLETED') {
          setDiscovering(false);
          fetchHighlights();
          if (onStatusChange) onStatusChange();
        } else if (data.status === 'FAILED') {
          setDiscovering(false);
          setError(data.error || 'Highlight discovery failed');
        }
      }
    } catch {
      // Ignore polling transient errors
    }
  };

  useEffect(() => {
    fetchHighlights();
    fetchStatus();
  }, [projectId]);

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (discovering) {
      interval = setInterval(fetchStatus, 1500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [discovering]);

  const handleStartDiscovery = async () => {
    try {
      setDiscovering(true);
      setError(null);
      const res = await fetch(`/api/projects/${projectId}/highlights/discover`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to start highlight discovery');
      }
      fetchStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Discovery start failed';
      setError(msg);
      setDiscovering(false);
    }
  };

  const handleToggleSelect = async (clip: Clip) => {
    try {
      setTogglingId(clip.id);
      const res = await fetch(`/api/projects/${projectId}/highlights/${clip.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected: !clip.selected }),
      });
      if (res.ok) {
        const updated: Clip = await res.json();
        setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update clip selection';
      setError(msg);
    } finally {
      setTogglingId(null);
    }
  };

  const formatTimestamp = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  const getCategoryIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case 'insight':
        return Lightbulb;
      case 'story':
        return BookOpen;
      case 'tutorial':
        return HelpCircle;
      default:
        return Flame;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Control */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-xl bg-slate-900/80 border border-slate-800">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            <h3 className="text-base font-bold text-white">AI Highlight Discovery (Stage 2.4)</h3>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-400/10 border border-amber-400/20 text-amber-400">
              Word-Index Anchored
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Semantic intelligence analyzes word-level speech to find high-retention 15s–90s clips with verified sentence boundaries.
          </p>
        </div>

        <button
          onClick={handleStartDiscovery}
          disabled={discovering || (projectStatus !== 'TRANSCRIBED' && projectStatus !== 'HIGHLIGHTS_READY')}
          className={`inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all shadow-md ${
            discovering
              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30 cursor-not-allowed'
              : 'bg-amber-400 hover:bg-amber-300 text-slate-950 shadow-amber-400/10'
          }`}
        >
          {discovering ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin text-amber-400" />
              <span>Analyzing Transcript...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>{clips.length > 0 ? 'Re-Run Discovery' : 'Discover AI Highlights'}</span>
            </>
          )}
        </button>
      </div>

      {/* Discovery Progress Indicator */}
      {discovering && statusInfo && (
        <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2 text-amber-300 font-medium">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>
                Running candidate extraction ({statusInfo.mode === 'llm' ? 'External LLM' : 'Offline Heuristic'} Mode)...
              </span>
            </div>
            <span className="font-mono text-amber-400 font-semibold">{statusInfo.progress_percent}%</span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-amber-400 h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${statusInfo.progress_percent}%` }}
            />
          </div>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div className="flex items-center space-x-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Candidate Clips List */}
      {loading && !discovering ? (
        <div className="p-8 text-center text-slate-500 text-xs">Loading candidate moments...</div>
      ) : clips.length === 0 ? (
        <div className="p-10 text-center rounded-xl border border-dashed border-slate-800 space-y-3">
          <Sparkles className="w-8 h-8 text-slate-600 mx-auto" />
          <div className="text-sm font-medium text-slate-300">No highlight clips discovered yet</div>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Click &quot;Discover AI Highlights&quot; above to parse the transcript and extract candidate moments.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <div className="text-xs text-slate-400">
              Discovered <span className="text-amber-400 font-semibold">{clips.length}</span> candidate clip(s) ranked by engagement:
            </div>
            <div className="text-xs text-slate-500">
              Selected: <span className="text-white font-semibold">{clips.filter((c) => c.selected).length}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {clips.map((clip, idx) => {
              const CategoryIcon = getCategoryIcon(clip.category);
              const durationSec = (clip.end_time - clip.start_time).toFixed(1);

              return (
                <div
                  key={clip.id}
                  className={`p-5 rounded-2xl border transition-all flex flex-col justify-between space-y-4 ${
                    clip.selected
                      ? 'bg-slate-900/90 border-amber-400/50 shadow-lg shadow-amber-400/5'
                      : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  {/* Card Header */}
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-slate-800 border border-slate-700/60 text-slate-300 text-[10px] font-medium uppercase tracking-wider">
                          <CategoryIcon className="w-3 h-3 text-amber-400" />
                          <span>{clip.category}</span>
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium ${
                            clip.validation_status === 'VALID'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}
                        >
                          {clip.validation_status}
                        </span>
                      </div>

                      {/* Engagement Score */}
                      <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-amber-400/10 border border-amber-400/20 text-amber-400 text-xs font-semibold">
                        <Star className="w-3.5 h-3.5 fill-amber-400" />
                        <span>{clip.engagement_score.toFixed(1)}</span>
                      </div>
                    </div>

                    {/* Title & Timing */}
                    <div>
                      <div className="text-xs text-slate-500 font-mono">#{idx + 1} Highlight</div>
                      <h4 className="text-sm font-bold text-white leading-snug">{clip.title}</h4>
                    </div>

                    {/* Hook Callout */}
                    {clip.hook && (
                      <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs space-y-1">
                        <div className="flex items-center space-x-1.5 text-amber-400/90 text-[11px] font-semibold">
                          <Quote className="w-3 h-3" />
                          <span>Opening Hook</span>
                        </div>
                        <p className="text-slate-300 italic leading-relaxed">&ldquo;{clip.hook}&rdquo;</p>
                      </div>
                    )}

                    {/* Description */}
                    {clip.description && (
                      <p className="text-xs text-slate-400 leading-relaxed">{clip.description}</p>
                    )}

                    {/* Rationale / Why AI selected this */}
                    {clip.rationale && (
                      <div className="text-[11px] text-slate-500 bg-slate-850/50 p-2.5 rounded-lg border border-slate-800/60">
                        <span className="font-semibold text-slate-400">Why Selected: </span>
                        {clip.rationale}
                      </div>
                    )}
                  </div>

                  {/* Card Footer */}
                  <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2 text-slate-400 font-mono text-[11px]">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      <span>{formatTimestamp(clip.start_time)}</span>
                      <span>&rarr;</span>
                      <span>{formatTimestamp(clip.end_time)}</span>
                      <span className="text-slate-500">({durationSec}s)</span>
                    </div>

                    <button
                      onClick={() => handleToggleSelect(clip)}
                      disabled={togglingId === clip.id}
                      className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        clip.selected
                          ? 'bg-amber-400 text-slate-950 font-semibold'
                          : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700'
                      }`}
                    >
                      {clip.selected ? (
                        <>
                          <Check className="w-3.5 h-3.5" />
                          <span>Selected</span>
                        </>
                      ) : (
                        <span>Select Clip</span>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
