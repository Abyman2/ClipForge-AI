import React from 'react';
import {
  Sparkles,
  FileText,
  FolderOpen,
  ArrowRight,
  Layers,
  Clock,
} from 'lucide-react';
import { Project } from '../types';
import { HighlightCandidatesView } from '../components/HighlightCandidatesView';

interface HighlightsViewProps {
  projects: Project[];
  selectedProject: Project | null;
  onSelectProject: (proj: Project) => void;
  onProjectsChange: () => void;
  onNavigateTab?: (tab: string) => void;
}

export const HighlightsView: React.FC<HighlightsViewProps> = ({
  projects,
  selectedProject,
  onSelectProject,
  onProjectsChange,
  onNavigateTab,
}) => {
  const formatDuration = (seconds: number) => {
    if (!seconds || seconds <= 0) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const isTranscribed =
    selectedProject &&
    (selectedProject.status === 'TRANSCRIBED' || selectedProject.status === 'HIGHLIGHTS_READY');

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner & Project Selector */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/80 border border-slate-800">
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <h2 className="text-lg font-bold text-white">AI Highlight Discovery Workspace (Stage 2.4)</h2>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-400/10 border border-amber-400/20 text-amber-400 font-semibold">
              Word-Index Anchored
            </span>
          </div>
          <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
            Semantic intelligence analyzes word-level speech to find high-retention 15s–90s clips with verified sentence boundaries.
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

      {/* Main Content Area */}
      {selectedProject ? (
        <div className="space-y-6">
          {/* Active Project Information Header */}
          <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300">
                <Layers className="w-4 h-4 text-amber-400" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">{selectedProject.title}</h3>
                <div className="flex items-center space-x-2 text-xs text-slate-400 font-mono">
                  <Clock className="w-3 h-3 text-slate-500" />
                  <span>{formatDuration(selectedProject.duration_seconds)}</span>
                  <span>•</span>
                  <span>Status: {selectedProject.status}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <span
                className={`text-[10px] font-mono px-2.5 py-1 rounded font-semibold ${
                  isTranscribed
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-amber-400/10 text-amber-400 border border-amber-400/20'
                }`}
              >
                {isTranscribed ? 'TRANSCRIPT READY' : 'TRANSCRIPT REQUIRED'}
              </span>
            </div>
          </div>

          {/* Transcript Readiness Check */}
          {isTranscribed ? (
            /* Dedicated Highlight Discovery & Candidate Review Canvas */
            <HighlightCandidatesView
              projectId={selectedProject.id}
              projectStatus={selectedProject.status}
              onStatusChange={onProjectsChange}
            />
          ) : (
            /* Warning / Call-to-action when project is not yet transcribed */
            <div className="p-12 text-center rounded-2xl border border-dashed border-slate-800 space-y-4 bg-slate-900/20">
              <div className="w-12 h-12 rounded-2xl bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400 mx-auto">
                <FileText className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <div className="text-base font-semibold text-slate-200">Transcript Required for AI Highlights</div>
                <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
                  ClipForge AI uses word-level transcript indices to discover and clamp candidate clips. Please transcribe this video in the Transcription workspace first.
                </p>
              </div>

              {onNavigateTab && (
                <div>
                  <button
                    onClick={() => onNavigateTab('transcribe')}
                    className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 text-xs font-semibold transition-colors shadow-md shadow-amber-400/10"
                  >
                    <span>Go to Transcription Workspace</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
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
