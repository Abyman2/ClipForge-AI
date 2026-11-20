import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatusCardProps {
  title: string;
  value: string;
  subtitle: string;
  icon: LucideIcon;
  badge?: string;
  badgeColor?: 'emerald' | 'amber' | 'slate';
}

export const StatusCard: React.FC<StatusCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  badge,
  badgeColor = 'slate',
}) => {
  const badgeClasses = {
    emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    amber: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    slate: 'bg-slate-800 text-slate-400 border-slate-700',
  };

  return (
    <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow-sm relative overflow-hidden">
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-medium text-slate-400 tracking-wide uppercase">{title}</span>
          <div className="text-xl font-bold text-slate-100 mt-1">{value}</div>
          <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/50">
          <Icon className="w-5 h-5 text-amber-400" />
        </div>
      </div>
      {badge && (
        <div className="mt-3">
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${badgeClasses[badgeColor]}`}>
            {badge}
          </span>
        </div>
      )}
    </div>
  );
};

