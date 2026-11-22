import React from 'react';
import { Sliders, Sparkles, Layers, Video, ShieldCheck, ArrowRight } from 'lucide-react';
import { Project } from '../types';

interface ClipStudioPlaceholderViewProps {
  selectedProject: Project | null;
  onNavigateTab?: (tab: string) => void;
}

export const ClipStudioPlaceholderView: React.FC<ClipStudioPlaceholderViewProps> = ({
  selectedProject,
  onNavigateTab,
}) => {
  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-6 rounded-2xl bg-slate-900/80 border border-slate-800">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400">
              <Sliders className="w-4 h-4" />
            </div>
            <h2 className="text-lg font-bold text-white">Clip Studio & 9:16 Vertical Video Engine</h2>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-400/10 border border-amber-400/20 text-amber-400 font-semibold">
              Stage 2.5 In Development
            </span>
          </div>
          <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
            Clip Studio handles vertical 9:16 video reframing, active speaker tracking, word-level synchronized karaoke subtitles, and local hardware-adaptive rendering.
          </p>
        </div>

        {selectedProject && onNavigateTab && (
          <button
            onClick={() => onNavigateTab('highlights')}
            className="inline-flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition-colors shrink-0"
          >
            <span>Review AI Highlights</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Feature Architecture Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-3">
          <div className="w-9 h-9 rounded-xl bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400">
            <Video className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-semibold text-white">Active Speaker 9:16 Reframing</h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            MediaPipe face detection tracks the active speaker across frames with shot-cut protection via PySceneDetect, preventing camera-whip artifacts.
          </p>
          <div className="text-[10px] font-mono text-slate-500 pt-1">
            Output: 1080 × 1920 (9:16 Vertical)
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-400/10 border border-emerald-400/20 flex items-center justify-center text-emerald-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-semibold text-white">ASS Karaoke Subtitles</h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            Advanced SubStation Alpha (<code className="text-amber-400 font-mono text-[11px]">.ass</code>) styles render word-by-word karaoke highlighting burned directly with FFmpeg libass.
          </p>
          <div className="text-[10px] font-mono text-slate-500 pt-1">
            Word-level synchrony • High retention
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-3">
          <div className="w-9 h-9 rounded-xl bg-sky-400/10 border border-sky-400/20 flex items-center justify-center text-sky-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-semibold text-white">Local CPU Encoding</h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            Targeted for your Intel Core i7-1255U using <code className="text-amber-400 font-mono text-[11px]">libx264 -preset fast -crf 20</code> and EBU R128 loudness normalization (-14 LUFS).
          </p>
          <div className="text-[10px] font-mono text-slate-500 pt-1">
            Zero cloud uploads • 100% private
          </div>
        </div>
      </div>

      {/* Selected Project Status Callout */}
      {selectedProject ? (
        <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs text-slate-400">Target Project Selected:</div>
              <div className="text-sm font-semibold text-white">{selectedProject.title}</div>
            </div>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-amber-400">
            {selectedProject.status}
          </span>
        </div>
      ) : (
        <div className="p-8 rounded-2xl border border-dashed border-slate-800 text-center text-xs text-slate-500">
          No video project selected. Choose or import a video project in the Video Ingest workspace.
        </div>
      )}
    </div>
  );
};
