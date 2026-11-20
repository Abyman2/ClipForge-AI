import React from 'react';
import { LayoutDashboard, Film, FileText, Sparkles, Sliders, Settings } from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onTabChange }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'import', label: 'Video Ingest', icon: Film, badge: 'Stage 2.2' },
    { id: 'transcribe', label: 'Transcription', icon: FileText, badge: 'Stage 2.3' },
    { id: 'highlights', label: 'AI Highlights', icon: Sparkles, badge: 'Stage 2.4' },
    { id: 'editor', label: 'Clip Studio', icon: Sliders, badge: 'Stage 2.5' },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900/40 p-4 flex flex-col justify-between">
      <nav className="space-y-1.5">
        <div className="text-[10px] font-semibold tracking-wider text-slate-500 uppercase px-3 mb-2">
          Workspace
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-amber-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 font-mono">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="p-3 rounded-lg bg-slate-850/80 border border-slate-800 text-xs space-y-1 text-slate-400">
        <div className="font-semibold text-slate-300">Phase 2.1 Foundation</div>
        <p className="text-[11px] leading-relaxed">
          SQLite WAL enabled. Local media engine interface initialized.
        </p>
      </div>
    </aside>
  );
};

