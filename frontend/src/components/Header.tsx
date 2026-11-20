import React from 'react';
import { Video, Cpu, HardDrive, ShieldCheck } from 'lucide-react';
import { HealthDiagnostic } from '../types';

interface HeaderProps {
  diagnostic: HealthDiagnostic | null;
}

export const Header: React.FC<HeaderProps> = ({ diagnostic }) => {
  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center space-x-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-amber-500 to-amber-300 flex items-center justify-center shadow-lg shadow-amber-500/20">
          <Video className="w-5 h-5 text-slate-950 font-bold" />
        </div>
        <div>
          <span className="font-bold text-lg tracking-tight text-slate-100">ClipForge</span>
          <span className="text-amber-400 font-semibold text-xs ml-1.5 px-1.5 py-0.5 rounded bg-amber-400/10 border border-amber-400/20">
            LOCAL AI
          </span>
        </div>
      </div>

      <div className="flex items-center space-x-4 text-xs text-slate-400">
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700/60">
          <Cpu className="w-3.5 h-3.5 text-slate-300" />
          <span>{diagnostic?.hardware.cpu_model || 'Intel Core i7-1255U'}</span>
        </div>

        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700/60">
          <HardDrive className="w-3.5 h-3.5 text-amber-400" />
          <span>{diagnostic ? `${diagnostic.hardware.disk_free_gb} GB Free` : 'Checking disk...'}</span>
        </div>

        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-medium">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>100% Local Media</span>
        </div>
      </div>
    </header>
  );
};

