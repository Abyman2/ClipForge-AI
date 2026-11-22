import React from 'react';
import { Settings, Cpu, Shield, Terminal, Database, Key } from 'lucide-react';
import { HealthDiagnostic } from '../types';

interface SettingsPlaceholderViewProps {
  diagnostic: HealthDiagnostic | null;
}

export const SettingsPlaceholderView: React.FC<SettingsPlaceholderViewProps> = ({ diagnostic }) => {
  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-6 rounded-2xl bg-slate-900/80 border border-slate-800">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400">
              <Settings className="w-4 h-4" />
            </div>
            <h2 className="text-lg font-bold text-white">Application Settings & Configuration</h2>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">
              Environment Profile
            </span>
          </div>
          <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
            ClipForge AI configuration is managed locally via <code className="text-amber-400 font-mono text-[11px]">.env</code> and system environment variables. All media processing parameters execute strictly on your workstation.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Hardware & Media Processing Defaults */}
        <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 text-sm font-semibold text-white border-b border-slate-800/80 pb-3">
            <Cpu className="w-4 h-4 text-amber-400" />
            <span>Hardware Execution Profile</span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Target Device</span>
              <span className="font-mono text-slate-200">
                {diagnostic?.hardware.recommended_device.toUpperCase() || 'CPU'}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Whisper Quantization</span>
              <span className="font-mono text-slate-200">
                {diagnostic?.hardware.recommended_compute_type || 'int8'}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Whisper Model Weight</span>
              <span className="font-mono text-slate-200">
                {diagnostic?.hardware.recommended_whisper_model || 'base'}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Logical Cores</span>
              <span className="font-mono text-slate-200">
                {diagnostic?.hardware.logical_cores || 12} Cores (4 Recommended Worker Threads)
              </span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">Video Encoding Preset</span>
              <span className="font-mono text-slate-200">
                {diagnostic?.hardware.ffmpeg_encoder || 'libx264'} (Fast, CRF 20)
              </span>
            </div>
          </div>
        </div>

        {/* External LLM Gateway Settings */}
        <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 text-sm font-semibold text-white border-b border-slate-800/80 pb-3">
            <Key className="w-4 h-4 text-amber-400" />
            <span>AI Highlight Intelligence Gateway</span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Protocol Support</span>
              <span className="font-mono text-slate-200">OpenAI-Compatible & Anthropic</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Fallback Heuristic Mode</span>
              <span className="font-mono text-emerald-400">Enabled (Zero Quota Offline)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Payload Boundary</span>
              <span className="font-mono text-slate-200">Text Word Indices Only (No Audio/Video)</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">API Key Privacy</span>
              <span className="font-mono text-slate-200">Scrubbed from logs (***REDACTED***)</span>
            </div>
          </div>
        </div>

        {/* Storage & Database Diagnostics */}
        <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 text-sm font-semibold text-white border-b border-slate-800/80 pb-3">
            <Database className="w-4 h-4 text-amber-400" />
            <span>Local Database & Storage</span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Database Engine</span>
              <span className="font-mono text-slate-200">SQLite 3 (WAL Mode)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Database Path</span>
              <span className="font-mono text-slate-400 truncate max-w-[200px]">
                {diagnostic?.database.path || 'clipforge-data/clipforge.db'}
              </span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">Available Storage Headroom</span>
              <span className="font-mono text-amber-400 font-semibold">
                {diagnostic?.hardware.disk_free_gb || '0'} GB Free (C: Drive)
              </span>
            </div>
          </div>
        </div>

        {/* Environment Security Note */}
        <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 text-sm font-semibold text-white border-b border-slate-800/80 pb-3">
            <Shield className="w-4 h-4 text-amber-400" />
            <span>Local-First Security Guarantee</span>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            ClipForge AI operates under a strict local-first processing model. Raw media files, extracted audio, face tracking data, and rendered videos are stored only on your local workstation and are never transmitted to external servers.
          </p>

          <div className="flex items-center space-x-2 p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-[11px] text-slate-400 font-mono">
            <Terminal className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span>Config File: .env (read on startup)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
