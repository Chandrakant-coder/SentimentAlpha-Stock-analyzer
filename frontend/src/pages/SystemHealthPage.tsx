import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Server,
  Database,
  Cpu,
  Folder,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { FinbertStatusBadge } from '../components/FinbertStatusBadge';

export const SystemHealthPage: React.FC = () => {
  const queryClient = useQueryClient();

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: apiClient.getSystemStatus,
    refetchInterval: 4000,
  });

  const { data: jobs, refetch: refetchJobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => apiClient.listJobs(25),
    refetchInterval: 3000,
  });

  const { data: marketStatuses, refetch: refetchMarket } = useQuery({
    queryKey: ['marketDataStatus'],
    queryFn: () => apiClient.getMarketDataStatus(),
    refetchInterval: 15000,
  });

  const marketSyncMutation = useMutation({
    mutationFn: () => apiClient.triggerMarketDataSync(),
    onSuccess: async (data) => {
      for (let i = 0; i < 60; i += 1) {
        const job = await apiClient.getJob(data.job_id);
        if (job.status === 'completed' || job.status === 'failed') break;
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      refetchMarket();
      refetchJobs();
    },
  });

  const ingestMutation = useMutation({
    mutationFn: apiClient.triggerIngestion,
    onSuccess: () => {
      refetchJobs();
      refetchStatus();
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => apiClient.triggerSentimentAnalysis(100),
    onSuccess: () => {
      refetchJobs();
      refetchStatus();
    },
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            SYSTEM HEALTH & PIPELINE MONITOR
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time audit of local FinBERT inference engine, SQLite storage, and background jobs.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => ingestMutation.mutate()}
            disabled={ingestMutation.isPending}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-mono border border-slate-700 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-cyan-400 ${ingestMutation.isPending ? 'animate-spin' : ''}`} />
            <span>Ingest News RSS</span>
          </button>

          <button
            onClick={() => analyzeMutation.mutate()}
            disabled={analyzeMutation.isPending}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-950/40 hover:bg-cyan-900/40 text-cyan-300 text-xs font-mono border border-cyan-800/60 transition-all disabled:opacity-50"
          >
            <Sparkles className={`w-3.5 h-3.5 text-cyan-400 ${analyzeMutation.isPending ? 'animate-spin' : ''}`} />
            <span>Analyze FinBERT</span>
          </button>

          <button
            onClick={() => marketSyncMutation.mutate()}
            disabled={marketSyncMutation.isPending}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-mono border border-slate-700 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-sky-400 ${marketSyncMutation.isPending ? 'animate-spin' : ''}`} />
            <span>Sync Market Data</span>
          </button>
        </div>
      </div>

      {/* Hardware & Service Diagnostics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 font-mono">
        {/* Card 1: API & DB */}
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>CORE BACKEND</span>
            <Server className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="my-2">
            <div className="text-lg font-bold text-white flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
              FastAPI Operational
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              SQLite Connected ({status?.database_connected ? 'Active' : 'Disconnected'})
            </div>
          </div>
          <div className="text-[10px] text-slate-500">
            Environment: {status?.environment || 'development'}
          </div>
        </div>

        {/* Card 2: Local FinBERT */}
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>FINBERT INFERENCE</span>
            <Cpu className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="my-2">
            <div className="mb-1">
              <FinbertStatusBadge />
            </div>
            <div className="text-[11px] text-slate-400">
              Hardware: <span className="text-white font-bold">{status?.finbert_device?.toUpperCase() || 'CPU'}</span>
            </div>
          </div>
          <div className="text-[10px] text-slate-500 truncate" title={status?.finbert_model_cache}>
            Cache: ...{status?.finbert_model_cache?.slice(-25)}
          </div>
        </div>

        {/* Card 3: Storage Metrics */}
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>KNOWLEDGE STORE</span>
            <Database className="w-4 h-4 text-sky-400" />
          </div>
          <div className="my-2">
            <div className="text-lg font-bold text-white">
              {status?.total_articles || 0} Articles
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              {status?.total_sentiment_analyzed || 0} Analyzed by FinBERT
            </div>
          </div>
          <div className="text-[10px] text-slate-500">
            Mapped Universe: {status?.total_stocks || 20} Nifty 50 Stocks
          </div>
        </div>

        {/* Card 4: Last Pipeline Sync */}
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>PIPELINE ENGINE</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="my-2">
            <div className="text-lg font-bold text-white">
              {status?.active_jobs || 0} Running Jobs
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              ThreadPool Worker Pool (3 workers)
            </div>
          </div>
          <div className="text-[10px] text-slate-500">
            Last News: {status?.last_ingestion_time ? status.last_ingestion_time.replace('T', ' ').slice(0, 16) : 'Never'}
          </div>
        </div>
      </div>

      <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800">
          <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
            Market Data Freshness (Yahoo daily bars)
          </span>
          <button onClick={() => refetchMarket()} className="text-[11px] font-mono text-slate-400 hover:text-white">
            Refresh
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                <th className="py-2 px-3">Symbol</th>
                <th className="py-2 px-3">Ticker</th>
                <th className="py-2 px-3">Status</th>
                <th className="py-2 px-3">Latest session</th>
                <th className="py-2 px-3">Expected session</th>
                <th className="py-2 px-3">Last success</th>
                <th className="py-2 px-3">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {marketStatuses && marketStatuses.length > 0 ? (
                marketStatuses.map((row) => (
                  <tr key={row.symbol}>
                    <td className="py-2 px-3 text-white">{row.symbol}</td>
                    <td className="py-2 px-3 text-cyan-400">{row.ticker}</td>
                    <td className="py-2 px-3">{row.stale ? 'STALE' : row.status}</td>
                    <td className="py-2 px-3">{row.latest_market_date?.slice(0, 10) || '—'}</td>
                    <td className="py-2 px-3">{row.expected_session_date || '—'}</td>
                    <td className="py-2 px-3">{row.last_success_at?.replace('T', ' ').slice(0, 16) || 'Never'}</td>
                    <td className="py-2 px-3 text-rose-400 truncate max-w-xs">{row.error || '—'}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-500">
                    No market-data diagnostics yet. Sync market data to populate this table.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Background Pipeline Jobs Table */}
      <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800">
          <span className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            Background Task History & Job Status Tracker
          </span>
          <button
            onClick={() => refetchJobs()}
            className="text-[11px] font-mono text-slate-400 hover:text-white flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Refresh</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                <th className="py-2.5 px-3">Job ID</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 w-40">Progress</th>
                <th className="py-2.5 px-3">Message</th>
                <th className="py-2.5 px-3">Processed</th>
                <th className="py-2.5 px-3">Started At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {jobs && jobs.length > 0 ? (
                jobs.map((job) => {
                  const isSuccess = job.status === 'completed';
                  const isRunning = job.status === 'running';
                  const isFailed = job.status === 'failed';

                  return (
                    <tr key={job.job_id} className="hover:bg-slate-900/60 transition-colors">
                      <td className="py-2 px-3 font-bold text-white">{job.job_id}</td>
                      <td className="py-2 px-3 uppercase text-cyan-400">{job.job_type}</td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            isSuccess
                              ? 'text-emerald-400 bg-emerald-950/80 border border-emerald-800/60'
                              : isRunning
                              ? 'text-cyan-400 bg-cyan-950/80 border border-cyan-800/60 animate-pulse'
                              : isFailed
                              ? 'text-rose-400 bg-rose-950/80 border border-rose-800/60'
                              : 'text-amber-400 bg-amber-950/80 border border-amber-800/60'
                          }`}
                        >
                          {job.status}
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden flex">
                          <div
                            className={`h-full transition-all ${
                              isFailed ? 'bg-rose-500' : isSuccess ? 'bg-emerald-500' : 'bg-cyan-500'
                            }`}
                            style={{ width: `${job.progress_pct}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-500">{job.progress_pct}%</span>
                      </td>
                      <td className="py-2 px-3 text-slate-300 truncate max-w-xs" title={job.message}>
                        {job.message || '—'}
                      </td>
                      <td className="py-2 px-3 text-slate-400">
                        {job.processed_items} / {job.total_items}
                      </td>
                      <td className="py-2 px-3 text-slate-500">
                        {job.started_at ? job.started_at.replace('T', ' ').slice(11, 19) : '—'}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-500">
                    No pipeline jobs executed yet. Trigger a task from the top bar.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
