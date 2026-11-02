import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Search,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  HelpCircle,
  ExternalLink,
  Activity,
  Layers,
  ChevronDown,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { apiClient } from '../api/client';
import { MarketFreshnessBanner } from '../components/MarketFreshnessBanner';
import {
  formatChartTick,
  formatInr,
  formatMarketDate,
  latestBar,
  previousBar,
} from '../utils/marketDisplay';

export const StockResearchPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSymbol = searchParams.get('symbol') || 'RELIANCE';
  const [selectedSymbol, setSelectedSymbol] = useState<string>(initialSymbol);
  const queryClient = useQueryClient();

  // Sync url param
  useEffect(() => {
    const sym = searchParams.get('symbol');
    if (sym && sym !== selectedSymbol) {
      setSelectedSymbol(sym);
    }
  }, [searchParams]);

  const { data: stocks } = useQuery({
    queryKey: ['stocks'],
    queryFn: () => apiClient.getStocks(),
  });

  const { data: stockInfo } = useQuery({
    queryKey: ['stock', selectedSymbol],
    queryFn: () => apiClient.getStock(selectedSymbol),
    enabled: !!selectedSymbol,
  });

  const { data: prices, isLoading: pricesLoading, isError: pricesError } = useQuery({
    queryKey: ['stockPrices', selectedSymbol],
    queryFn: () => apiClient.getStockPrices(selectedSymbol, 120),
    enabled: !!selectedSymbol,
    staleTime: 0,            // always refetch when the query is invalidated
    refetchOnWindowFocus: true,
  });

  const { data: marketStatus } = useQuery({
    queryKey: ['marketDataStatus', selectedSymbol],
    queryFn: () => apiClient.getStockMarketStatus(selectedSymbol),
    enabled: !!selectedSymbol,
    staleTime: 0,
    refetchOnWindowFocus: true,
  });

  const refreshPrices = useMutation({
    mutationFn: () => apiClient.syncStockPrices(selectedSymbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stockPrices', selectedSymbol] });
      queryClient.invalidateQueries({ queryKey: ['marketDataStatus', selectedSymbol] });
    },
  });

  const { data: factors } = useQuery({
    queryKey: ['stockFactors', selectedSymbol],
    queryFn: () => apiClient.getStockFactors(selectedSymbol, 60),
    enabled: !!selectedSymbol,
  });

  const { data: signals } = useQuery({
    queryKey: ['stockSignals', selectedSymbol],
    queryFn: () => apiClient.getSignals({ symbol: selectedSymbol }),
    enabled: !!selectedSymbol,
  });

  const { data: newsData } = useQuery({
    queryKey: ['stockNews', selectedSymbol],
    queryFn: () => apiClient.getNews({ symbol: selectedSymbol, page: 1, page_size: 10 }),
    enabled: !!selectedSymbol,
  });

  const currentSignal = signals && signals.length > 0 ? signals[0] : null;

  const latestPrice = latestBar(prices);
  const prevPrice = previousBar(prices);
  const priceChange = latestPrice && prevPrice ? ((latestPrice.close - prevPrice.close) / prevPrice.close) * 100 : 0;

  const handleSelectSymbol = (sym: string) => {
    setSelectedSymbol(sym);
    setSearchParams({ symbol: sym });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Search & Stock Selector Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={selectedSymbol}
              onChange={(e) => handleSelectSymbol(e.target.value)}
              className="appearance-none bg-[#0e1626] border border-slate-700/80 text-white font-mono font-bold text-sm rounded-lg px-4 py-2 pr-9 focus:outline-none focus:border-cyan-500 cursor-pointer"
            >
              {stocks?.map((s) => (
                <option key={s.symbol} value={s.symbol} className="bg-slate-900 text-white">
                  {s.symbol} — {s.company_name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          <div className="text-xs font-mono text-slate-400 hidden sm:block">
            {stockInfo?.company_name} • <span className="text-cyan-400">{stockInfo?.sector}</span>
          </div>
        </div>

        {/* Price & Change Pill */}
        {latestPrice && (
          <div className="flex items-center gap-4 font-mono">
            <div>
              <div className="text-[10px] text-slate-400 uppercase">Unadjusted close · INR</div>
              <div className="text-base font-bold text-white">{formatInr(latestPrice.close)}</div>
              <div className="text-[10px] text-slate-500">Session {formatMarketDate(latestPrice.date)}</div>
            </div>
            <div
              className={`flex items-center text-xs font-semibold px-2.5 py-1 rounded-md ${priceChange >= 0
                ? 'text-emerald-400 bg-emerald-950/60 border border-emerald-800/60'
                : 'text-rose-400 bg-rose-950/60 border border-rose-800/60'
                }`}
            >
              {priceChange >= 0 ? '+' : ''}
              {priceChange.toFixed(2)}%
            </div>
          </div>
        )}
      </div>

      <MarketFreshnessBanner
        status={marketStatus}
        onRefresh={() => refreshPrices.mutate()}
        refreshing={refreshPrices.isPending}
      />

      {/* Key Technical & Sentiment Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono">
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-lg p-3">
          <div className="text-[10px] text-slate-400">RSI (14)</div>
          <div className="text-sm font-bold text-white mt-1">
            {latestPrice?.rsi_14 ? latestPrice.rsi_14.toFixed(1) : '—'}
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">
            {latestPrice?.rsi_14 && latestPrice.rsi_14 > 70 ? 'Overbought' : latestPrice?.rsi_14 && latestPrice.rsi_14 < 30 ? 'Oversold' : 'Neutral'}
          </div>
        </div>

        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-lg p-3">
          <div className="text-[10px] text-slate-400">MA (20-Day)</div>
          <div className="text-sm font-bold text-cyan-400 mt-1">
            {latestPrice?.ma_20 ? formatInr(latestPrice.ma_20) : '—'}
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">Short Trend</div>
        </div>

        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-lg p-3">
          <div className="text-[10px] text-slate-400">MA (50-Day)</div>
          <div className="text-sm font-bold text-amber-400 mt-1">
            {latestPrice?.ma_50 ? formatInr(latestPrice.ma_50) : '—'}
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">Medium Trend</div>
        </div>

        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-lg p-3">
          <div className="text-[10px] text-slate-400">Volatility (20d)</div>
          <div className="text-sm font-bold text-white mt-1">
            {latestPrice?.volatility_20d ? `${(latestPrice.volatility_20d * 100).toFixed(2)}%` : '—'}
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">Rolling Std</div>
        </div>

        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-lg p-3">
          <div className="text-[10px] text-slate-400">Momentum (20d)</div>
          <div className={`text-sm font-bold mt-1 ${latestPrice?.momentum_20d && latestPrice.momentum_20d >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {latestPrice?.momentum_20d ? `${(latestPrice.momentum_20d * 100).toFixed(2)}%` : '—'}
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">Past 20 Sessions</div>
        </div>

        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-lg p-3">
          <div className="text-[10px] text-slate-400">Volume Ratio</div>
          <div className="text-sm font-bold text-white mt-1">
            {latestPrice?.volume_ratio ? `${latestPrice.volume_ratio.toFixed(2)}x` : '—'}
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">vs 20d Average</div>
        </div>
      </div>

      {/* Research Signal Card */}
      {currentSignal && (
        <div className="bg-gradient-to-r from-[#0d1627] to-[#0c1322] border border-cyan-800/40 rounded-xl p-5 shadow-lg">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-3">
              <span
                className={`px-3 py-1 rounded text-xs font-mono font-bold tracking-wider ${currentSignal.signal_type === 'BUY'
                  ? 'bg-emerald-500 text-slate-950 shadow-[0_0_12px_#10b981]'
                  : currentSignal.signal_type === 'SELL'
                    ? 'bg-rose-500 text-slate-950 shadow-[0_0_12px_#f43f5e]'
                    : 'bg-slate-700 text-white'
                  }`}
              >
                {currentSignal.signal_type} CANDIDATE
              </span>
              <span className="text-xs font-mono text-slate-300">
                Confidence: <span className="text-white font-bold">{(currentSignal.confidence * 100).toFixed(0)}%</span>
              </span>
              <span className="text-[11px] font-mono text-slate-500">
                Strategy: {currentSignal.strategy}
              </span>
            </div>
            <div className="text-[10px] font-mono text-slate-400">
              Evaluated on: {currentSignal.signal_date.split('T')[0]}
            </div>
          </div>

          <div className="mt-3 space-y-2">
            <div className="text-xs text-slate-200 font-sans leading-relaxed">
              <span className="font-mono text-cyan-400 font-bold uppercase mr-1">Explanation:</span>
              {currentSignal.explanation}
            </div>

            {currentSignal.risk_warning && (
              <div className="flex items-start gap-2 text-xs text-amber-300/90 font-mono bg-amber-950/20 border border-amber-800/30 p-2 rounded">
                <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <span>{currentSignal.risk_warning}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Historical Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Price and Moving Averages */}
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800/80">
            <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              Price Action & Moving Averages (unadjusted OHLC)
            </span>
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="text-cyan-400">• Close</span>
              <span className="text-emerald-400">• MA20</span>
              <span className="text-amber-400">• MA50</span>
            </div>
          </div>

          <div className="h-72 w-full">
            {prices && prices.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={prices} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(val) => formatChartTick(String(val))}
                    stroke="#64748b"
                    fontSize={11}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    stroke="#64748b"
                    fontSize={11}
                    tickFormatter={(val) => formatInr(Number(val))}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }}
                    labelFormatter={(label) => `Session: ${formatMarketDate(String(label))}`}
                    formatter={(val: any, name: any) => [
                      formatInr(Number(val)),
                      name === 'close' || name === 'Close' ? 'Close (unadjusted, INR)' : String(name),
                    ]}
                  />
                  <Line type="monotone" dataKey="close" stroke="#38bdf8" strokeWidth={2} dot={false} name="Close" />
                  <Line type="monotone" dataKey="ma_20" stroke="#10b981" strokeWidth={1.5} dot={false} strokeDasharray="4 4" name="MA 20" />
                  <Line type="monotone" dataKey="ma_50" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="2 2" name="MA 50" />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500 font-mono text-xs">
                {pricesLoading
                  ? 'Loading stored prices...'
                  : pricesError
                    ? 'Could not load stored prices.'
                    : 'No stored Yahoo daily bars. Use Refresh prices.'}
              </div>
            )}
          </div>
        </div>

        {/* Chart 2: Daily Sentiment Factors */}
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800/80">
            <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              Sentiment Factor Trends
            </span>
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="text-emerald-400">• Weighted Sent</span>
              <span className="text-cyan-400">• 7d Rolling</span>
              <span className="text-indigo-400">• 14d Rolling</span>
            </div>
          </div>

          <div className="h-72 w-full">
            {factors && factors.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={factors} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(val) => formatChartTick(String(val))}
                    stroke="#64748b"
                    fontSize={11}
                  />
                  <YAxis
                    domain={[-1, 1]}
                    stroke="#64748b"
                    fontSize={11}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }}
                    labelFormatter={(label) => `News/factor date: ${formatMarketDate(String(label))}`}
                  />
                  <Bar dataKey="confidence_weighted_sentiment" fill="#10b981" fillOpacity={0.6} name="Daily Weighted" />
                  <Line type="monotone" dataKey="rolling_7d_mean" stroke="#38bdf8" strokeWidth={2} dot={false} name="7d Rolling" />
                  <Line type="monotone" dataKey="rolling_14d_mean" stroke="#818cf8" strokeWidth={1.5} dot={false} strokeDasharray="3 3" name="14d Rolling" />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500 font-mono text-xs">
                No daily sentiment factors generated yet. Run FinBERT analysis first.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stock Specific Article Timeline */}
      <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800">
          <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
            {selectedSymbol} Intelligence Feed & Article Breakdown
          </span>
          <span className="text-xs font-mono text-slate-400">
            {newsData?.total || 0} Total Mentions
          </span>
        </div>

        <div className="space-y-3">
          {newsData?.items && newsData.items.length > 0 ? (
            newsData.items.map((art) => {
              const sent = art.sentiment;
              const isPos = sent?.sentiment_label === 'positive';
              const isNeg = sent?.sentiment_label === 'negative';

              return (
                <div
                  key={art.id}
                  className="p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 hover:border-slate-700 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-1 max-w-3xl">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-slate-400">{art.source}</span>
                      <span className="text-slate-600">•</span>
                      <span className="text-[10px] font-mono text-slate-500">{art.published_at.split('T')[0]}</span>
                    </div>
                    <a
                      href={art.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-semibold text-slate-200 hover:text-cyan-400 flex items-center gap-1.5 transition-colors"
                    >
                      <span>{art.title}</span>
                      <ExternalLink className="w-3 h-3 text-slate-500 shrink-0" />
                    </a>
                    {art.description && (
                      <p className="text-[11px] text-slate-400 line-clamp-2">{art.description}</p>
                    )}
                  </div>

                  {sent ? (
                    <div className="shrink-0 flex flex-col items-end gap-1 font-mono">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-bold px-2 py-0.5 rounded ${isPos
                            ? 'text-emerald-400 bg-emerald-950/80 border border-emerald-800/80'
                            : isNeg
                              ? 'text-rose-400 bg-rose-950/80 border border-rose-800/80'
                              : 'text-slate-300 bg-slate-800/80 border border-slate-700'
                            }`}
                        >
                          {sent.sentiment_label.toUpperCase()} ({sent.sentiment_score > 0 ? '+' : ''}
                          {sent.sentiment_score.toFixed(2)})
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 flex gap-2">
                        <span>Pos: {(sent.positive_probability * 100).toFixed(0)}%</span>
                        <span>Neu: {(sent.neutral_probability * 100).toFixed(0)}%</span>
                        <span>Neg: {(sent.negative_probability * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs font-mono text-amber-400 bg-amber-950/40 border border-amber-800/40 px-2 py-1 rounded">
                      Inference Pending
                    </span>
                  )}
                </div>
              );
            })
          ) : (
            <div className="text-xs font-mono text-slate-500 text-center py-8">
              No news mapped to {selectedSymbol} in the current dataset. Ingest feeds from the sidebar.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
