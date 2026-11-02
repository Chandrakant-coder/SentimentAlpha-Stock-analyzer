/** Chart/API date helpers. Never convert ISO dates through the browser timezone. */

export function marketDateKey(value: string | undefined | null): string {
  if (!value) return '';
  const raw = String(value);
  const isoDay = raw.match(/^(\d{4}-\d{2}-\d{2})/);
  return isoDay ? isoDay[1] : raw.slice(0, 10);
}

export function formatMarketDate(value: string | undefined | null): string {
  const key = marketDateKey(value);
  return key || '—';
}

export function formatChartTick(value: string | undefined | null): string {
  const key = marketDateKey(value);
  return key.length === 10 ? key.slice(5) : key;
}

export function formatInr(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return `₹${Number(value).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function latestBar<T extends { date: string }>(bars: T[] | undefined | null): T | null {
  if (!bars || bars.length === 0) return null;
  const sorted = [...bars].sort((a, b) => marketDateKey(a.date).localeCompare(marketDateKey(b.date)));
  return sorted[sorted.length - 1];
}

export function previousBar<T extends { date: string }>(bars: T[] | undefined | null): T | null {
  if (!bars || bars.length < 2) return null;
  const sorted = [...bars].sort((a, b) => marketDateKey(a.date).localeCompare(marketDateKey(b.date)));
  return sorted[sorted.length - 2];
}

export type MarketStatusLike = {
  stale?: boolean;
  missing_expected_session?: boolean;
  status?: string;
  error?: string | null;
  latest_market_date?: string | null;
  expected_session_date?: string | null;
  last_success_at?: string | null;
};

export function freshnessWarning(status: MarketStatusLike | undefined | null): string | null {
  if (!status) return null;
  if (status.status === 'failed') {
    return `Market-data refresh failed${status.error ? `: ${status.error}` : ''}. Showing last stored session ${formatMarketDate(status.latest_market_date)}.`;
  }
  if (status.status === 'empty' || status.status === 'never') {
    return 'No Yahoo Finance daily bars stored yet. Trigger a market-data sync.';
  }
  if (status.missing_expected_session) {
    return `Latest stored session is ${formatMarketDate(status.latest_market_date)}; expected NSE session is ${status.expected_session_date || 'the prior weekday'}. Yahoo daily bars are delayed historical closes, not a live quote.`;
  }
  if (status.stale) {
    return 'Stored market data may be behind the latest available NSE session.';
  }
  return null;
}
