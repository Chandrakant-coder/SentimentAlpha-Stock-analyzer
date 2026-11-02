/**
 * Shows a compact market-data freshness badge.
 * Green  = latest stored session matches the expected NSE session
 * Amber  = latest session is behind (stale)
 * Red    = last sync failed
 * Grey   = never synced / unknown
 */
import React from 'react';
import { CheckCircle2, AlertCircle, XCircle, HelpCircle } from 'lucide-react';

export type SyncStatusLike = {
    status?: string;
    stale?: boolean;
    missing_expected_session?: boolean;
    latest_market_date?: string | null;
    expected_session_date?: string | null;
    error?: string | null;
};

export const SyncStatusBadge: React.FC<{ status?: SyncStatusLike | null }> = ({ status }) => {
    if (!status) {
        return (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border border-slate-700 text-slate-400 bg-slate-900">
                <HelpCircle className="w-3 h-3" />
                unknown
            </span>
        );
    }

    const isFailed = status.status === 'failed';
    const isNever = status.status === 'never' || status.status === 'empty';
    const isStale = !isFailed && !isNever && (status.stale || status.missing_expected_session);
    const isGood = !isFailed && !isNever && !isStale;

    if (isFailed) {
        return (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border border-rose-800/60 text-rose-400 bg-rose-950/40" title={status.error || 'Sync failed'}>
                <XCircle className="w-3 h-3" />
                sync failed
            </span>
        );
    }
    if (isNever) {
        return (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border border-amber-800/60 text-amber-400 bg-amber-950/40">
                <HelpCircle className="w-3 h-3" />
                not synced
            </span>
        );
    }
    if (isStale) {
        return (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border border-amber-800/60 text-amber-400 bg-amber-950/40" title={`Expected: ${status.expected_session_date} — Latest: ${status.latest_market_date?.slice(0, 10)}`}>
                <AlertCircle className="w-3 h-3" />
                stale · {status.latest_market_date?.slice(0, 10) ?? '—'}
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border border-emerald-800/60 text-emerald-400 bg-emerald-950/40" title={`Latest session: ${status.latest_market_date?.slice(0, 10)}`}>
            <CheckCircle2 className="w-3 h-3" />
            {status.latest_market_date?.slice(0, 10) ?? '—'}
        </span>
    );
};
