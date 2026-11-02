import React from 'react';
import { AlertCircle } from 'lucide-react';
import { formatMarketDate, freshnessWarning, type MarketStatusLike } from '../utils/marketDisplay';

export const MarketFreshnessBanner: React.FC<{
  status?: MarketStatusLike | null;
  onRefresh?: () => void;
  refreshing?: boolean;
}> = ({ status, onRefresh, refreshing }) => {
  const warning = freshnessWarning(status || undefined);
  if (!status && !warning) return null;

  return (
    <div
      className={`flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg border px-3 py-2 text-[11px] font-mono ${
        warning
          ? 'border-amber-800/70 bg-amber-950/30 text-amber-200'
          : 'border-slate-800 bg-slate-900/40 text-slate-400'
      }`}
    >
      <div className="flex items-start gap-2">
        {warning && <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-400" />}
        <div>
          <div>
            Latest stored session: <span className="text-white">{formatMarketDate(status?.latest_market_date)}</span>
            {' · '}Expected weekday session: <span className="text-white">{status?.expected_session_date || '—'}</span>
            {' · '}Last successful sync: <span className="text-white">{formatMarketDate(status?.last_success_at)}</span>
          </div>
          <div className="mt-0.5">
            {warning || 'Yahoo Finance daily bars (unadjusted close, INR). Delayed historical session data, not a live quote.'}
          </div>
        </div>
      </div>
      {onRefresh && (
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="shrink-0 px-2.5 py-1 rounded border border-cyan-800/70 text-cyan-300 hover:bg-cyan-950/40 disabled:opacity-50"
        >
          {refreshing ? 'Refreshing…' : 'Refresh prices'}
        </button>
      )}
    </div>
  );
};
