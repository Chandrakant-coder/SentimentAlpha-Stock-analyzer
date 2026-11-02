import { describe, expect, it } from 'vitest';
import {
  formatChartTick,
  formatInr,
  formatMarketDate,
  freshnessWarning,
  latestBar,
  marketDateKey,
  previousBar,
} from './marketDisplay';

describe('marketDisplay', () => {
  it('uses the ISO calendar date and does not invent today', () => {
    expect(marketDateKey('2026-10-23T00:00:00')).toBe('2026-10-23');
    expect(marketDateKey('2026-10-23T18:30:00Z')).toBe('2026-10-23');
    expect(formatMarketDate('2026-10-22T00:00:00')).toBe('2026-10-22');
    expect(formatChartTick('2026-10-23T00:00:00')).toBe('10-23');
    expect(formatMarketDate(undefined)).toBe('—');
  });

  it('formats unadjusted close in INR', () => {
    expect(formatInr(11230)).toBe('₹11,230.00');
    expect(formatInr(1184.5)).toBe('₹1,184.50');
  });

  it('selects the latest bar by market date, not array order', () => {
    const bars = [
      { date: '2026-10-23T00:00:00', close: 1400 },
      { date: '2026-10-21T00:00:00', close: 1380 },
      { date: '2026-10-22T00:00:00', close: 1390 },
    ];
    expect(latestBar(bars)?.close).toBe(1400);
    expect(marketDateKey(latestBar(bars)?.date)).toBe('2026-10-23');
    expect(previousBar(bars)?.close).toBe(1390);
  });

  it('surfaces stale and failed sync warnings without fabricating prices', () => {
    expect(
      freshnessWarning({
        status: 'failed',
        error: 'timed out',
        latest_market_date: '2026-10-22T00:00:00',
      })
    ).toContain('2026-10-22');

    expect(
      freshnessWarning({
        status: 'success',
        missing_expected_session: true,
        latest_market_date: '2026-10-22T00:00:00',
        expected_session_date: '2026-10-23',
      })
    ).toContain('2026-10-23');

    expect(
      freshnessWarning({
        status: 'success',
        stale: false,
        missing_expected_session: false,
        latest_market_date: '2026-10-23T00:00:00',
      })
    ).toBeNull();
  });
});
