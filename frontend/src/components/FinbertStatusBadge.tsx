import React from 'react';
import { Cpu, CheckCircle2, AlertCircle, RefreshCw, Download } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';

export const FinbertStatusBadge: React.FC = () => {
  const { data: status } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: apiClient.getSystemStatus,
    refetchInterval: 5000,
  });

  const finbertStatus = status?.finbert_status || 'not_downloaded';

  const getStatusConfig = () => {
    switch (finbertStatus) {
      case 'ready':
        return {
          label: 'FinBERT Ready',
          color: 'text-emerald-400 bg-emerald-950/60 border-emerald-800/80',
          dot: 'bg-emerald-400 shadow-[0_0_8px_#34d399]',
          icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />,
        };
      case 'loading':
        return {
          label: 'FinBERT Loading',
          color: 'text-amber-400 bg-amber-950/60 border-amber-800/80',
          dot: 'bg-amber-400 animate-ping',
          icon: <RefreshCw className="w-3.5 h-3.5 text-amber-400 animate-spin" />,
        };
      case 'downloading':
        return {
          label: 'FinBERT Downloading',
          color: 'text-cyan-400 bg-cyan-950/60 border-cyan-800/80',
          dot: 'bg-cyan-400 animate-pulse',
          icon: <Download className="w-3.5 h-3.5 text-cyan-400 animate-bounce" />,
        };
      case 'failed':
        return {
          label: 'FinBERT Error',
          color: 'text-rose-400 bg-rose-950/60 border-rose-800/80',
          dot: 'bg-rose-400',
          icon: <AlertCircle className="w-3.5 h-3.5 text-rose-400" />,
        };
      default:
        return {
          label: 'FinBERT Offline',
          color: 'text-slate-400 bg-slate-900 border-slate-700',
          dot: 'bg-slate-400',
          icon: <Cpu className="w-3.5 h-3.5 text-slate-400" />,
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div
      className={`flex items-center gap-2 px-2.5 py-1 rounded-md text-xs font-mono font-medium border transition-colors ${config.color}`}
      title={`Local FinBERT: ${finbertStatus.toUpperCase()} (${status?.finbert_device || 'cpu'})`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.icon}
      <span>{config.label}</span>
      <span className="text-[10px] opacity-60 uppercase">[{status?.finbert_device || 'cpu'}]</span>
    </div>
  );
};
