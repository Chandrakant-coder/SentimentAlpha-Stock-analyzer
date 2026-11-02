import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  LineChart,
  Newspaper,
  BrainCircuit,
  Sliders,
  Activity,
  RefreshCw,
  Sparkles,
  ChevronRight,
} from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { FinbertStatusBadge } from '../components/FinbertStatusBadge';

export const DashboardLayout: React.FC = () => {
  const queryClient = useQueryClient();
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const ingestMutation = useMutation({
    mutationFn: apiClient.triggerIngestion,
    onSuccess: (data) => {
      setActionFeedback(`Ingestion queued: ${data.job_id}`);
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setTimeout(() => setActionFeedback(null), 4000);
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => apiClient.triggerSentimentAnalysis(50),
    onSuccess: (data) => {
      setActionFeedback(`Sentiment analysis queued: ${data.job_id}`);
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setTimeout(() => setActionFeedback(null), 4000);
    },
  });

  const marketSyncMutation = useMutation({
    mutationFn: () => apiClient.triggerMarketDataSync(),
    onSuccess: async (data) => {
      setActionFeedback(`Market data sync queued: ${data.job_id}`);
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      for (let i = 0; i < 60; i += 1) {
        const job = await apiClient.getJob(data.job_id);
        if (job.status === 'completed' || job.status === 'failed') {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      queryClient.invalidateQueries({ queryKey: ['stockPrices'] });
      queryClient.invalidateQueries({ queryKey: ['marketDataStatus'] });
      queryClient.invalidateQueries({ queryKey: ['allLatestPrices'] });
      setTimeout(() => setActionFeedback(null), 4000);
    },
  });

  const navItems = [
    { name: 'Market Overview', path: '/', icon: LayoutDashboard },
    { name: 'Stock Research', path: '/research', icon: LineChart },
    { name: 'News Explorer', path: '/news', icon: Newspaper },
    { name: 'ML Lab', path: '/ml-lab', icon: BrainCircuit },
    { name: 'Backtesting Lab', path: '/backtesting', icon: Sliders },
    { name: 'System Health', path: '/health', icon: Activity },
  ];

  return (
    <div className="flex h-screen w-full bg-[#090d16] text-slate-100 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800/80 bg-[#0c1220]/95 flex flex-col justify-between shrink-0">
        <div>
          {/* Logo / Terminal Header */}
          <div className="p-4 border-b border-slate-800/80 flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded bg-gradient-to-tr from-cyan-600 to-sky-400 flex items-center justify-center font-mono font-bold text-slate-950 text-sm shadow-[0_0_12px_rgba(56,189,248,0.3)]">
                α
              </div>
              <span className="font-mono font-bold text-base tracking-wider text-white">
                SENTIMENT<span className="text-cyan-400">ALPHA</span>
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-mono tracking-tight">
              <span>LOCAL AI QUANT PLATFORM</span>
              <span className="text-slate-600">•</span>
              <span className="text-cyan-400">NIFTY 50</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${isActive
                      ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shadow-[0_0_15px_rgba(6,182,212,0.1)]'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.name}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Bottom Status / Quick Pipeline Actions */}
        <div className="p-4 border-t border-slate-800/80 bg-[#0a0f1d] flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Model Engine</span>
            <FinbertStatusBadge />
          </div>

          <div className="flex flex-col gap-1.5">
            <button
              onClick={() => ingestMutation.mutate()}
              disabled={ingestMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-md bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 text-xs font-mono border border-slate-700/80 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-cyan-400 ${ingestMutation.isPending ? 'animate-spin' : ''}`} />
              <span>Fetch News RSS</span>
            </button>

            <button
              onClick={() => analyzeMutation.mutate()}
              disabled={analyzeMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-md bg-cyan-950/40 hover:bg-cyan-900/40 text-cyan-300 text-xs font-mono border border-cyan-800/60 transition-all disabled:opacity-50"
            >
              <Sparkles className={`w-3.5 h-3.5 text-cyan-400 ${analyzeMutation.isPending ? 'animate-spin' : ''}`} />
              <span>Run Local FinBERT</span>
            </button>

            <button
              onClick={() => marketSyncMutation.mutate()}
              disabled={marketSyncMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-md bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 text-xs font-mono border border-slate-700/80 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-sky-400 ${marketSyncMutation.isPending ? 'animate-spin' : ''}`} />
              <span>Sync Market Data</span>
            </button>
          </div>

          {actionFeedback && (
            <div className="text-[11px] text-emerald-400 font-mono bg-emerald-950/40 border border-emerald-800/40 px-2 py-1 rounded text-center animate-fade-in">
              {actionFeedback}
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-gradient-to-b from-[#090d16] to-[#0c111e]">
        <Outlet />
      </main>
    </div>
  );
};
