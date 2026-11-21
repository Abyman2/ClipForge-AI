import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { StatusCard } from './components/StatusCard';
import { VideoIngestView } from './views/VideoIngestView';
import { HealthDiagnostic } from './types';
import { Database, Cpu, Activity, Video, Sparkles, CheckCircle2, ArrowRight } from 'lucide-react';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [diagnostic, setDiagnostic] = useState<HealthDiagnostic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/health');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: HealthDiagnostic = await res.json();
      setDiagnostic(data);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to connect to ClipForge backend';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Header diagnostic={diagnostic} />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar currentTab={currentTab} onTabChange={setCurrentTab} />

        <main className="flex-1 overflow-y-auto p-8 space-y-8">
          {currentTab === 'import' || currentTab === 'transcribe' || currentTab === 'highlights' ? (
            <VideoIngestView />
          ) : (
            <>
              {/* Welcome Banner */}
              <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800 p-8">
                <div className="max-w-2xl relative z-10 space-y-4">
                  <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-full bg-amber-400/10 border border-amber-400/20 text-amber-400 text-xs font-medium">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Stage 2.4 — AI Highlight Discovery & Boundary Validation Active</span>
                  </div>
                  <h1 className="text-3xl font-extrabold tracking-tight text-white">
                    Transform Long-Form Content Into Viral 9:16 Shorts
                  </h1>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    ClipForge AI runs 100% locally on your Intel Core i7-1255U workstation.
                    Heavy video and audio streams never leave your machine, keeping your footage private, secure, and fast.
                  </p>
                  <div>
                    <button
                      onClick={() => setCurrentTab('import')}
                      className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-semibold text-xs transition-colors shadow-lg shadow-amber-400/10"
                    >
                      <span>Ingest Video Footage</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="absolute right-6 top-1/2 -translate-y-1/2 opacity-10 pointer-events-none">
                  <Video className="w-64 h-64 text-amber-400" />
                </div>
              </div>

              {/* System Status Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatusCard
                  title="Backend API"
                  value={diagnostic ? diagnostic.status.toUpperCase() : (loading ? 'CONNECTING...' : 'OFFLINE')}
                  subtitle="FastAPI / Uvicorn Service"
                  icon={Activity}
                  badge={diagnostic ? `v${diagnostic.version}` : undefined}
                  badgeColor="emerald"
                />

                <StatusCard
                  title="Local Database"
                  value={diagnostic ? diagnostic.database.status.toUpperCase() : 'UNKNOWN'}
                  subtitle={diagnostic ? `Journal: ${diagnostic.database.journal_mode}` : 'SQLite 3'}
                  icon={Database}
                  badge="WAL Mode"
                  badgeColor="emerald"
                />

                <StatusCard
                  title="Compute Profile"
                  value={diagnostic ? diagnostic.hardware.recommended_device.toUpperCase() : 'CPU'}
                  subtitle="Optimized for Intel Iris Xe"
                  icon={Cpu}
                  badge={diagnostic ? `Whisper: ${diagnostic.hardware.recommended_compute_type}` : 'CPU int8'}
                  badgeColor="amber"
                />

                <StatusCard
                  title="Pipeline Engine"
                  value="STAGE 2.2"
                  subtitle="Ingest & FFprobe Ready"
                  icon={CheckCircle2}
                  badge="Stage 2.2 Active"
                  badgeColor="emerald"
                />
              </div>

              {/* Diagnostics Detail Box */}
              <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-slate-100">Workstation Diagnostic Telemetry</h3>
                    <p className="text-xs text-slate-400">Live hardware profile and media capabilities</p>
                  </div>
                  <button
                    onClick={fetchHealth}
                    className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
                  >
                    Refresh Telemetry
                  </button>
                </div>

                {error && (
                  <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                    Backend connection error: {error}. Verify that the FastAPI backend is running on port 8000.
                  </div>
                )}

                {diagnostic && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
                    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 space-y-1">
                      <span className="text-slate-500">OPERATING SYSTEM</span>
                      <div className="text-slate-200">{diagnostic.hardware.os}</div>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 space-y-1">
                      <span className="text-slate-500">STORAGE HEADROOM</span>
                      <div className="text-slate-200">{diagnostic.hardware.disk_free_gb} GB Free (SSD)</div>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 space-y-1">
                      <span className="text-slate-500">MEDIA CAPABILITIES</span>
                      <div className="text-slate-200">
                        FFmpeg: {diagnostic.media_tools.ffmpeg_available ? 'Available' : 'Interface Ready (CLI pending)'}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
};

